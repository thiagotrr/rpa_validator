"""Persistência. Firestore em produção; memória em testes/dev. Datas viram 'AAAA-MM-DD' (Firestore não aceita date)."""

import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass, fields
from datetime import date, datetime
from typing import Protocol

from app.dominio import AbaPlanilha, LinhaPlanilha, LinhaSemRecibo, RpaExtraido

COL_PLANILHA = "planilha_conferencia"  # 1 documento por competência + empresa (metadados da aba)
COL_PLANILHA_CONTEUDO = "planilha_conferencia_conteudo"  # 1 documento por LINHA da planilha
COL_RPAS = "rpas"  # 1 documento por RPA: competência + número
COL_TENTATIVAS = "tentativas_acesso"
TIPO_LINHA_RPA = "rpa"
TIPO_LINHA_SEM_RECIBO = "sem_recibo"
_LOTE_FIRESTORE = 400  # limite do batch é 500 operações


@dataclass(frozen=True)
class TentativasLogin:
    falhas: int
    primeira_falha: datetime
    bloqueado_ate: datetime | None


def id_documento_planilha(competencia: str, codigo_empresa: str) -> str:
    return f"{competencia}_{codigo_empresa}"


def id_documento_linha(competencia: str, codigo_empresa: str, numero_linha: int) -> str:
    """'2026-10_671_00009' — a linha da planilha é a identidade, inclusive para linhas sem recibo."""
    return f"{competencia}_{codigo_empresa}_{numero_linha:05d}"


def id_documento_rpa(competencia: str, numero_rpa: str) -> str:
    """Spec: identificação = ano/mês da carga + número do RPA."""
    return f"{competencia}_{numero_rpa}"


def _para_documento(obj) -> dict:
    d = asdict(obj)
    for k, v in d.items():
        if isinstance(v, date) and not isinstance(v, datetime):
            d[k] = v.isoformat()
        elif isinstance(v, tuple):
            d[k] = list(v)
    return d


def _de_documento(cls, d: dict):
    kw = {}
    for f in fields(cls):
        v = d.get(f.name)
        if f.name.startswith("data_") and isinstance(v, str):
            v = date.fromisoformat(v)
        elif isinstance(v, list):
            v = tuple(v)
        kw[f.name] = v if v is not None or f.name != "conteudo" else {}
    return cls(**kw)


def linha_para_documento(ln: LinhaPlanilha) -> dict:
    return _para_documento(ln) | {"tipo_linha": TIPO_LINHA_RPA}


def linha_sem_recibo_para_documento(aba: AbaPlanilha, ln: LinhaSemRecibo) -> dict:
    return {
        "competencia": aba.competencia,
        "codigo_empresa": aba.codigo_empresa,
        "cnpj": aba.cnpj,
        "aba": aba.aba,
        "numero_linha": ln.numero_linha,
        "conteudo": ln.conteudo,
        "tipo_linha": TIPO_LINHA_SEM_RECIBO,
    }


def documento_para_linha(d: dict) -> LinhaPlanilha:
    return _de_documento(LinhaPlanilha, d)


def rpa_para_documento(r: RpaExtraido) -> dict:
    return _para_documento(r)


def documento_para_rpa(d: dict) -> RpaExtraido:
    return _de_documento(RpaExtraido, d)


def _documentos_da_aba(aba: AbaPlanilha) -> dict[str, dict]:
    docs = {
        id_documento_linha(aba.competencia, aba.codigo_empresa, ln.numero_linha): linha_para_documento(ln)
        for ln in aba.linhas
    }
    docs |= {
        id_documento_linha(aba.competencia, aba.codigo_empresa, ln.numero_linha): linha_sem_recibo_para_documento(
            aba, ln
        )
        for ln in aba.linhas_sem_recibo
    }
    return docs


def _metadados_aba(aba: AbaPlanilha, arquivo: str, usuario: str, agora: datetime) -> dict:
    return {
        "competencia": aba.competencia,
        "codigo_empresa": aba.codigo_empresa,
        "cnpj": aba.cnpj,
        "aba": aba.aba,
        "arquivo": arquivo,
        "qtd_linhas": len(aba.linhas),
        "qtd_linhas_sem_recibo": len(aba.linhas_sem_recibo),
        "carregado_por": usuario,
        "carregado_em": agora,
    }


def _documentos_da_competencia(
    competencia: str, abas: list[AbaPlanilha], arquivo: str, usuario: str, agora: datetime
) -> tuple[dict[str, dict], dict[str, dict]]:
    """-> (conteúdo por id, metadados por id) da planilha inteira. Recusa lote vazio ou de outra competência."""
    if not abas:
        raise ValueError("planilha sem abas: nada a gravar")
    erradas = sorted({a.competencia for a in abas if a.competencia != competencia})
    if erradas:
        raise ValueError(f"abas com competência diferente de {competencia}: {', '.join(erradas)}")
    conteudo: dict[str, dict] = {}
    for aba in abas:
        conteudo |= _documentos_da_aba(aba)
    metadados = {
        id_documento_planilha(competencia, a.codigo_empresa): _metadados_aba(a, arquivo, usuario, agora) for a in abas
    }
    return conteudo, metadados


class Repositorio(Protocol):
    def substituir_planilha(
        self, competencia: str, abas: list[AbaPlanilha], *, arquivo: str, usuario: str, agora: datetime
    ) -> None: ...
    def listar_planilha(self, competencia: str) -> list[LinhaPlanilha]: ...
    def salvar_rpa(self, rpa: RpaExtraido, *, usuario: str, agora: datetime) -> None: ...
    def listar_rpas(self, competencia: str) -> list[RpaExtraido]: ...
    def numeros_rpas(self, competencia: str) -> set[str]: ...
    def obter_tentativas(self, chave: str) -> TentativasLogin | None: ...
    def salvar_tentativas(self, chave: str, t: TentativasLogin) -> None: ...
    def atualizar_tentativas(
        self, chave: str, funcao: Callable[[TentativasLogin | None], TentativasLogin]
    ) -> TentativasLogin: ...
    def limpar_tentativas(self, chave: str) -> None: ...


class RepositorioMemoria:
    def __init__(self) -> None:
        self.planilha: dict[str, dict] = {}
        self.conteudo: dict[str, dict] = {}
        self.rpas: dict[str, dict] = {}
        self.tentativas: dict[str, TentativasLogin] = {}
        self._trava_tentativas = threading.Lock()

    def substituir_planilha(self, competencia, abas, *, arquivo, usuario, agora):
        """Planilha nova SUBSTITUI a competência inteira: grava a nova e depois apaga o que sobrou da antiga."""
        conteudo, metadados = _documentos_da_competencia(competencia, abas, arquivo, usuario, agora)
        self.conteudo |= conteudo
        self.planilha |= metadados
        for k in [k for k, d in self.conteudo.items() if d["competencia"] == competencia and k not in conteudo]:
            del self.conteudo[k]
        for k in [k for k, d in self.planilha.items() if d["competencia"] == competencia and k not in metadados]:
            del self.planilha[k]

    def listar_planilha(self, competencia):
        docs = (
            d for d in self.conteudo.values() if d["competencia"] == competencia and d["tipo_linha"] == TIPO_LINHA_RPA
        )
        return sorted((documento_para_linha(d) for d in docs), key=lambda ln: (ln.codigo_empresa, ln.numero_rpa))

    def salvar_rpa(self, rpa, *, usuario, agora):
        self.rpas[id_documento_rpa(rpa.competencia, rpa.numero_rpa)] = rpa_para_documento(rpa) | {
            "carregado_por": usuario,
            "carregado_em": agora,
        }

    def listar_rpas(self, competencia):
        return sorted(
            (documento_para_rpa(d) for d in self.rpas.values() if d["competencia"] == competencia),
            key=lambda r: r.numero_rpa,
        )

    def numeros_rpas(self, competencia):
        return {d["numero_rpa"] for d in self.rpas.values() if d["competencia"] == competencia}

    def obter_tentativas(self, chave):
        return self.tentativas.get(chave)

    def salvar_tentativas(self, chave, t):
        self.tentativas[chave] = t

    def atualizar_tentativas(self, chave, funcao):
        """Ler-alterar-gravar sem perder contagem sob requisições paralelas."""
        with self._trava_tentativas:
            novo = funcao(self.tentativas.get(chave))
            self.tentativas[chave] = novo
            return novo

    def limpar_tentativas(self, chave):
        self.tentativas.pop(chave, None)


class RepositorioFirestore:
    def __init__(self, project: str | None = None, database: str = "(default)") -> None:
        from google.cloud import firestore

        self.db = firestore.Client(project=project, database=database)

    @staticmethod
    def _filtro(campo, valor):
        from google.cloud.firestore_v1.base_query import FieldFilter

        return FieldFilter(campo, "==", valor)

    def _gravar_em_lotes(self, operacoes):
        for i in range(0, len(operacoes), _LOTE_FIRESTORE):
            batch = self.db.batch()
            for op in operacoes[i : i + _LOTE_FIRESTORE]:
                op(batch)
            batch.commit()

    def _da_competencia(self, colecao: str, competencia: str):
        return self.db.collection(colecao).where(filter=self._filtro("competencia", competencia)).stream()

    def substituir_planilha(self, competencia, abas, *, arquivo, usuario, agora):
        """Grava a planilha nova (mesmos ids são sobrescritos) e só então apaga o que sobrou da antiga.
        Assim a competência nunca fica vazia no meio da carga; se cair no meio, repetir a carga resolve."""
        conteudo, metadados = _documentos_da_competencia(competencia, abas, arquivo, usuario, agora)
        col, col_meta = self.db.collection(COL_PLANILHA_CONTEUDO), self.db.collection(COL_PLANILHA)
        ops = [lambda b, i=i, d=d: b.set(col.document(i), d) for i, d in conteudo.items()]
        ops += [lambda b, i=i, d=d: b.set(col_meta.document(i), d) for i, d in metadados.items()]
        self._gravar_em_lotes(ops)
        sobras = [d.reference for d in self._da_competencia(COL_PLANILHA_CONTEUDO, competencia) if d.id not in conteudo]
        sobras += [d.reference for d in self._da_competencia(COL_PLANILHA, competencia) if d.id not in metadados]
        self._gravar_em_lotes([lambda b, ref=ref: b.delete(ref) for ref in sobras])

    def listar_planilha(self, competencia):
        docs = (
            self.db.collection(COL_PLANILHA_CONTEUDO)
            .where(filter=self._filtro("competencia", competencia))
            .where(filter=self._filtro("tipo_linha", TIPO_LINHA_RPA))
            .stream()
        )
        return sorted(
            (documento_para_linha(d.to_dict()) for d in docs), key=lambda ln: (ln.codigo_empresa, ln.numero_rpa)
        )

    def salvar_rpa(self, rpa, *, usuario, agora):
        self.db.collection(COL_RPAS).document(id_documento_rpa(rpa.competencia, rpa.numero_rpa)).set(
            rpa_para_documento(rpa) | {"carregado_por": usuario, "carregado_em": agora}
        )

    def listar_rpas(self, competencia):
        docs = self._da_competencia(COL_RPAS, competencia)
        return sorted((documento_para_rpa(d.to_dict()) for d in docs), key=lambda r: r.numero_rpa)

    def numeros_rpas(self, competencia):
        return {d.to_dict()["numero_rpa"] for d in self._da_competencia(COL_RPAS, competencia)}

    def obter_tentativas(self, chave):
        snap = self.db.collection(COL_TENTATIVAS).document(chave).get()
        if not snap.exists:
            return None
        d = snap.to_dict()
        return TentativasLogin(d["falhas"], d["primeira_falha"], d.get("bloqueado_ate"))

    def salvar_tentativas(self, chave, t):
        self.db.collection(COL_TENTATIVAS).document(chave).set(asdict(t))

    def atualizar_tentativas(self, chave, funcao):
        """Transação do Firestore: leitura e gravação atômicas (a transação é repetida em caso de conflito)."""
        from google.cloud import firestore

        ref = self.db.collection(COL_TENTATIVAS).document(chave)

        @firestore.transactional
        def na_transacao(transacao):
            snap = ref.get(transaction=transacao)
            atual = None
            if snap.exists:
                d = snap.to_dict()
                atual = TentativasLogin(d["falhas"], d["primeira_falha"], d.get("bloqueado_ate"))
            novo = funcao(atual)
            transacao.set(ref, asdict(novo))
            return novo

        return na_transacao(self.db.transaction(max_attempts=20))  # padrão (5) esgota sob contenção

    def limpar_tentativas(self, chave):
        self.db.collection(COL_TENTATIVAS).document(chave).delete()


def criar_repositorio(backend: str, project: str | None, database: str) -> Repositorio:
    if backend == "memory":
        return RepositorioMemoria()
    if backend == "firestore":
        return RepositorioFirestore(project, database)
    raise ValueError(f"REPOSITORY_BACKEND inválido: {backend}")
