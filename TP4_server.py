"""\
GLO-2000 Travail pratique 4 - Serveur
Noms et numéros étudiants:
-
-
-
"""

from email.message import EmailMessage
import hashlib
import hmac
import json
import os
import select
import smtplib
import socket
import sys
import re

import glosocket
import gloutils


class Server:
    """Serveur mail @glo2000.ca."""

    def __init__(self) -> None:
        """
        Prépare le socket du serveur `_server_socket`
        et le met en mode écoute.

        Prépare les attributs suivants:
        - `_client_socs` une liste des sockets clients.
        - `_logged_users` un dictionnaire associant chaque
            socket client à un nom d'utilisateur.

        S'assure que les dossiers de données du serveur existent.
        """

        self._server_socket = self._make_server_socket("127.0.0.1", gloutils.APP_PORT)
        print(f"DEBUGGING : server socket : {self._server_socket}")
        self._client_socs: list[socket.socket] = []
        self._logged_users = {}
        if not os.path.exists(gloutils.SERVER_DATA_DIR):
            os.makedirs(gloutils.SERVER_DATA_DIR)
        server_lost_dir_path = os.path.join(gloutils.SERVER_DATA_DIR, gloutils.SERVER_LOST_DIR)
        if not os.path.exists(server_lost_dir_path):
            os.makedirs(server_lost_dir_path)
        while True :
            select.select(_accept_client(self))
            

    def cleanup(self) -> None:
        """Ferme toutes les connexions résiduelles."""
        for client_soc in self._client_socs:
            client_soc.close()
        self._server_socket.close()

    def _make_server_socket(self, source: str, port: int) -> socket.socket:
        """ setup for the server socket """
        try:
            server_soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # IPV4, TCP
            server_soc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_soc.bind((source, port))
            server_soc.listen()

            return server_soc
        except glosocket.GLOSocketError:
            print("Something went wrong when opening the server's socket")
            sys.exit(-1)

    def _accept_client(self) -> None:
        """Accepte un nouveau client."""
        client_socket, _ = self._server_socket.accept()
        self._client_socs.append(client_socket)

    def _remove_client(self, client_soc: socket.socket) -> None:
        """Retire le client des structures de données et ferme sa connexion."""
        self._client_socs.remove(client_soc)

    def _create_account(self, client_soc: socket.socket,
                        payload: gloutils.AuthPayload
                        ) -> gloutils.GloMessage:
        """
        Crée un compte à partir des données du payload.

        Si les identifiants sont valides, créee le dossier de l'utilisateur,
        associe le socket au nouvel l'utilisateur et retourne un succès,
        sinon retourne un message d'erreur.
        """
        print(f"DEBUGGING : creating a new account with payload : {payload}")
        # TODO : ajouter validation des identifiants
        # TODO : créer le dossier de l'utilisateur
        # TODO : associer le socket au nouvel utilisateur
        username = payload['username']
        password = payload['password']
        # Vérifier le string nom utilisateur
        if re.search(r"[^._-\w]", username) is not None:
            errorPayload = ErrorPayload(error_message="le nom d’utilisateur contient des caractères autres que alphanumériques,_, . ou -.")
            return gloutils.GloMessage(header= gloutils.Headers.ERROR, payload=errorPayload)
        #Vérifier que le dossier n'existe pas ou le créer
        user_dir_path = os.path.join(gloutils.SERVER_DATA_DIR, username.upper())
        if os.path.exists(user_dir_path) :
            errorPayload = ErrorPayload(error_message="ce nom d'utilisateur existe déjà")
            return gloutils.GloMessage(header= gloutils.Headers.ERROR, payload=errorPayload)
        else :
            os.makedirs(user_dir_path)
        #Vérifier le mot de passe
        if len(password)<10 or re.search(r"[a-z]+[A-Z]+[0-9]+", password) is None :
            errorPayload = ErrorPayload(error_message="le mot de passe a moins de 10 caractères et/ou ne contient pas au moins une majuscule, une minuscule et un chiffre")
            return gloutils.GloMessage(header=gloutils.Headers.ERROR, payload = errorPayload)
        #Hacher et sauvegarder le mot de passe
        password_file_path = os.path.join(user_dir_path, gloutils.PASSWORD_FILENAME)
        password_file = open(password_file_path, "w+")
        gfg = hashlib.sha3_512()
        gfg.update(password)
        password_file.write(gfg.digest())
        password_file.close()
        #Associer le socket au nouvel utilisateur
        self._logged_users.add[client_soc]=username
        return gloutils.GloMessage(header=gloutils.Headers.OK)

    def _login(self, client_soc: socket.socket, payload: gloutils.AuthPayload
               ) -> gloutils.GloMessage:
        """
        Vérifie que les données fournies correspondent à un compte existant.

        Si les identifiants sont valides, associe le socket à l'utilisateur et
        retourne un succès, sinon retourne un message d'erreur.
        """
        print(f"DEBUGGING : login for payload : {payload}")
        username = payload['username']
        password = payload['password']
        #S'assurer que l'utilisateur existe
        user_dir_path = os.path.join(gloutils.SERVER_DATA_DIR, username.upper())
        if  not os.path.exists(user_dir_path) :
            errorPayload = ErrorPayload(error_message="cet utilisateur n'existe pas")
            return gloutils.GloMessage(header= gloutils.Headers.ERROR, payload=errorPayload)
        #Hacher le mot de passe et le vérifier
        password_file_path = os.path.join(user_dir_path, gloutils.PASSWORD_FILENAME)
        password_file = open(password_file_path, "r+")
        hash_password = password_file.read()
        password_file.close()  
        gfg = hashlib.sha3_512()
        gfg.update(password)
        if not gfg.digest() == hash_password :
            errorPayload = ErrorPayload(error_message="mauvais mot de passe")
            return gloutils.GloMessage(header= gloutils.Headers.ERROR, payload=errorPayload)
        self._logged_users.add[client_soc]=username
        successPayload = gloutils.AuthPayload(username=username, password=password)
        return gloutils.GloMessage(header=gloutils.Headers.OK, payload=payload)


    def _logout(self, client_soc: socket.socket) -> None:
        """Déconnecte un utilisateur."""
        print(f"DEBUGGING : logging out user - disconnection socket {client_soc}")
        client_soc.close()

    def _get_email_list(self, client_soc: socket.socket
                        ) -> gloutils.GloMessage:
        """
        Récupère la liste des courriels de l'utilisateur associé au socket.
        Les éléments de la liste sont construits à l'aide du gabarit
        SUBJECT_DISPLAY et sont ordonnés du plus récent au plus ancien.

        Une absence de courriel n'est pas une erreur, mais une liste vide.
        """
        print(f"DEBUGGING : get email list")
        return gloutils.GloMessage()

    def _get_email(self, client_soc: socket.socket,
                   payload: gloutils.EmailChoicePayload
                   ) -> gloutils.GloMessage:
        """
        Récupère le contenu de l'email dans le dossier de l'utilisateur associé
        au socket.
        """
        print(f"DEBUGGING : get email for payload : {payload}")
        return gloutils.GloMessage()

    def _get_stats(self, client_soc: socket.socket) -> gloutils.GloMessage:
        """
        Récupère le nombre de courriels et la taille du dossier et des fichiers
        de l'utilisateur associé au socket.
        """
        print(f"DEBUGGING : get stats")
        return gloutils.GloMessage()

    def _send_email(self, payload: gloutils.EmailContentPayload
                    ) -> gloutils.GloMessage:
        """
        Détermine si l'envoi est interne ou externe et:
        - Si l'envoi est interne, écris le message tel quel dans le dossier
        du destinataire.
        - Si le destinataire n'existe pas, place le message dans le dossier
        SERVER_LOST_DIR et considère l'envoi comme un échec.
        - Si le destinataire est externe, transforme le message en
        EmailMessage et utilise le serveur SMTP pour le relayer.

        Retourne un messange indiquant le succès ou l'échec de l'opération.
        """
        print(f"DEBUGGING : send email for payload {payload}")
        
        
        return gloutils.GloMessage()

    def run(self):
        """Point d'entrée du serveur."""
        while True:
            # Select readable sockets
            result = select.select(self._client_socs + [self._server_socket], [], [])
            waiters: list[socket.socket] = result[0]
            for waiter in waiters:
                if waiter == self._server_socket:
                    self._accept_client()
                else:
                    self._process_client(waiter)

    def _process_client(self, client_socket: socket.socket):
        try:
            message = glosocket.recv_msg(client_socket)
            print(f"DEBUGGING : message received : {message}")
        except glosocket.GLOSocketError as e:
            print(f"an exeption occured : {e}")
            self._remove_client(client_socket)
            return

        match json.loads(message):
            case {"header": gloutils.Headers.AUTH_REGISTER, "payload": payload}:
                self._send(client_socket, self._create_account(client_socket, payload))
            case {"header": gloutils.Headers.AUTH_LOGIN, "payload": payload}:
                self._send(client_socket, self._login(client_socket, payload))
            case {"header": gloutils.Headers.AUTH_LOGOUT}:
                self._logout(client_socket)
            case {"header": gloutils.Headers.INBOX_READING_REQUEST}:
                self._send(client_socket, self._get_email_list(client_socket))
            case {"header": gloutils.Headers.INBOX_READING_CHOICE, "payload": payload}:
                self._send(client_socket, self._get_email(payload))
            case {"header": gloutils.Headers.EMAIL_SENDING, "payload": payload}:
                self._send(client_socket, self._send_email(payload))
            case {"header": gloutils.Headers.STATS_REQUEST}:
                self._send(client_socket, self._get_stats(client_socket))
            case {"header": gloutils.Headers.BYE}:
                self._remove_client(client_socket)

    def _send(self, dest: socket.socket, payload) -> None:
        try:
            glosocket.send_msg(dest, json.dumps(payload))
        except glosocket.GLOSocketError as e:
            print(f"error : {e}")
            self._remove_client(dest)


def _main() -> int:
    server = Server()
    try:
        server.run()
    except KeyboardInterrupt:
        server.cleanup()
    return 0


if __name__ == '__main__':
    sys.exit(_main())
