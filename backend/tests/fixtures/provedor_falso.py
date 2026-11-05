"""ProvedorIdentidade em memória para testes (sem Firebase)."""

from datetime import datetime, timedelta

from app.autenticacao import CredenciaisInvalidas, SessaoAcesso, TokenInvalido


class ProvedorFalso:
    def __init__(self, usuarios: dict[str, str], autorizados: set[str]):
        self.usuarios = usuarios  # email -> senha
        self.autorizados = autorizados
        self.revogados: set[str] = set()

    def _sessao(self, email: str, agora: datetime) -> SessaoAcesso:
        return SessaoAcesso(f"id:{email}:{int(agora.timestamp())}", f"rt:{email}", agora + timedelta(hours=1))

    def entrar_com_senha(self, email, senha, agora):
        if self.usuarios.get(email) != senha:
            raise CredenciaisInvalidas()
        return self._sessao(email, agora)

    def renovar_sessao(self, refresh_token, agora):
        email = refresh_token.removeprefix("rt:")
        if not refresh_token.startswith("rt:") or email in self.revogados:
            raise TokenInvalido("refresh token inválido")
        return self._sessao(email, agora)

    def verificar_token(self, id_token):
        partes = id_token.split(":")
        if len(partes) != 3 or partes[0] != "id" or partes[1] in self.revogados:
            raise TokenInvalido("token inválido")
        return {"email": partes[1], "rpa_autorizado": partes[1] in self.autorizados}
