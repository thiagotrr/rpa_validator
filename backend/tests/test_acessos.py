from app.acessos import UsuarioAcesso, ler_lista_emails, sincronizar_acessos


class AdminFalso:
    def __init__(self, existentes=(), autorizados=()):
        self.usuarios = {e: UsuarioAcesso(f"uid-{e}", e) for e in [*existentes, *autorizados]}
        self.autorizados = set(autorizados)
        self.revogados: list[str] = []

    def obter_por_email(self, email):
        return self.usuarios.get(email)

    def criar(self, email):
        self.usuarios[email] = UsuarioAcesso(f"uid-{email}", email)
        return self.usuarios[email]

    def definir_autorizacao(self, uid, autorizado):
        email = uid.removeprefix("uid-")
        (self.autorizados.add if autorizado else self.autorizados.discard)(email)

    def revogar_sessoes(self, uid):
        self.revogados.append(uid)

    def listar_autorizados(self):
        return [self.usuarios[e] for e in sorted(self.autorizados)]

    def gerar_link_definicao_senha(self, email):
        return f"https://link/{email}"


def test_ler_lista_emails():
    texto = "# equipe\nAna@Empresa.com\n bia@empresa.com ; ana@empresa.com\n\ninvalido@\ncarlos@empresa.com # gestor\n"
    assert ler_lista_emails(texto) == (["ana@empresa.com", "bia@empresa.com", "carlos@empresa.com"], ["invalido@"])


def test_cria_novos_autoriza_existentes_e_gera_link_so_para_novos():
    admin = AdminFalso(existentes=["bia@empresa.com"], autorizados=["carlos@empresa.com"])
    r = sincronizar_acessos(["ana@empresa.com", "bia@empresa.com", "carlos@empresa.com"], admin)
    assert (r.criados, r.autorizados, r.ja_autorizados) == (
        ["ana@empresa.com"],
        ["ana@empresa.com", "bia@empresa.com"],
        ["carlos@empresa.com"],
    )
    assert r.links_definicao_senha == {"ana@empresa.com": "https://link/ana@empresa.com"}
    assert admin.autorizados == {"ana@empresa.com", "bia@empresa.com", "carlos@empresa.com"}


def test_remover_ausentes_tira_claim_e_revoga_sessoes():
    admin = AdminFalso(autorizados=["ana@empresa.com", "saiu@empresa.com"])
    r = sincronizar_acessos(["ana@empresa.com"], admin, remover_ausentes=True)
    assert r.removidos == ["saiu@empresa.com"]
    assert admin.autorizados == {"ana@empresa.com"} and admin.revogados == ["uid-saiu@empresa.com"]


def test_sem_remover_ausentes_ninguem_perde_acesso():
    admin = AdminFalso(autorizados=["saiu@empresa.com"])
    assert sincronizar_acessos([], admin).removidos == []
    assert admin.autorizados == {"saiu@empresa.com"}


def test_simulacao_nao_altera_nada():
    admin = AdminFalso(autorizados=["saiu@empresa.com"])
    r = sincronizar_acessos(["novo@empresa.com"], admin, remover_ausentes=True, simular=True)
    assert (r.criados, r.removidos) == (["novo@empresa.com"], ["saiu@empresa.com"])
    assert admin.autorizados == {"saiu@empresa.com"} and "novo@empresa.com" not in admin.usuarios
    assert r.links_definicao_senha == {}
