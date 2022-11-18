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

SCALES = ["", "K", "M", "G", "T", "P", "E", "Z", "Y", "Br"]

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
        self._client_socs: list[socket.socket] = []
        self._logged_users = {}

        if not os.path.exists(gloutils.SERVER_DATA_DIR):
            os.makedirs(gloutils.SERVER_DATA_DIR)
        server_lost_dir_path = os.path.join(gloutils.SERVER_DATA_DIR, gloutils.SERVER_LOST_DIR)
        if not os.path.exists(server_lost_dir_path):
            os.makedirs(server_lost_dir_path)

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
        self._logout(client_soc)
        client_soc.close()

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
        username = payload['username']
        password = payload['password']
        user_dir_path = os.path.join(gloutils.SERVER_DATA_DIR, username.upper())

        if not _is_username_valid(username):
            return _error_message(f"le nom d’utilisateur {username} contient des caractères autres que alphanumériques,_, . ou -.")
        if not _is_password_valid(password):
            return _error_message("le mot de passe a moins de 10 caractères et/ou ne contient pas au moins une majuscule, une minuscule et un chiffre")
        if os.path.exists(user_dir_path):
            return _error_message("ce nom d'utilisateur existe déjà")

        os.makedirs(user_dir_path)
        _save_password(user_dir_path, password)

        self._link_socket_to_user(client_soc, username)
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
        user_dir_path = os.path.join(gloutils.SERVER_DATA_DIR, username.upper())

        if not os.path.exists(user_dir_path):
            return _error_message("cet utilisateur n'existe pas")

        saved_password = _read_password(user_dir_path)
        given_password = _hash_password(password)
        if not given_password == saved_password:
            return _error_message("mauvais mot de passe")

        self._link_socket_to_user(client_soc, username)
        return _success_message(gloutils.AuthPayload(username=username, password=password))

    def _link_socket_to_user(self, client_soc: socket.socket, username: str) -> None:
        self._logged_users[client_soc] = username

    def _logout(self, client_soc: socket.socket) -> None:
        """Déconnecte un utilisateur."""
        print(f"DEBUGGING : logging out user - disconnection socket {client_soc}")
        self._client_socs.remove(client_soc)

    def _get_email_list(self, client_soc: socket.socket
                        ) -> gloutils.GloMessage:
        """
        Récupère la liste des courriels de l'utilisateur associé au socket.
        Les éléments de la liste sont construits à l'aide du gabarit
        SUBJECT_DISPLAY et sont ordonnés du plus récent au plus ancien.

        Une absence de courriel n'est pas une erreur, mais une liste vide.
        """
        username = self._logged_users[client_soc]
        email_list = self._get_sorted_email_list(username)
        subject_display_list = []

        for i, data in enumerate(email_list, start=1):
            subject = gloutils.SUBJECT_DISPLAY.format(
                number=i,
                sender=data["sender"],
                subject=data["subject"],
                date=data["date"]
            )
            subject_display_list.append(subject)

        return _success_message(gloutils.EmailListPayload(email_list=subject_display_list))

    def _get_sorted_email_list(self, username: str) -> list:
        """
        Retourne la liste triée par date des emails en format json présents 
        dans le dossier utilisateur
        """
        user_dir_path = os.path.join(gloutils.SERVER_DATA_DIR, username.upper())
        user_emails = os.listdir(user_dir_path)
        user_emails.remove(gloutils.PASSWORD_FILENAME)
        email_data_list = []

        for email_file in user_emails:
            file_path = os.path.join(user_dir_path, email_file)
            email_file = open(file_path, encoding='utf-8')
            email_data = json.load(email_file)
            email_data_list.append(email_data)
            email_file.close()

        emails_sorted_list = sorted(email_data_list,
                                    key=lambda data: data['date'],
                                    reverse=True)
        return emails_sorted_list
    
    def _get_email(self, client_soc: socket.socket,
                   payload: gloutils.EmailChoicePayload
                   ) -> gloutils.GloMessage:
        """
        Récupère le contenu de l'email dans le dossier de l'utilisateur associé
        au socket.
        """
        username = self._logged_users[client_soc]
        choice = int(payload['choice'])
        email = self._get_sorted_email_list(username)[choice-1]

        return _success_message(_email_content_payload(email))

    def _get_stats(self, client_soc: socket.socket) -> gloutils.GloMessage:
        """
        Récupère le nombre de courriels et la taille du dossier et des fichiers
        de l'utilisateur associé au socket.
        """
        print(f"DEBUGGING : get stats")
        username = self._logged_users[client_soc]
        user_dir = os.path.join(gloutils.SERVER_DATA_DIR, username.upper())
        list_emails = os.listdir(user_dir)
        list_emails.remove(gloutils.PASSWORD_FILENAME)

        if list_emails is None:
            nb_emails = 0
        else : 
            nb_emails = len(list_emails)

        user_dir_size = 0
        for (current_dir, sousDossiers, files) in os.walk(user_dir):
            user_dir_size += sum(os.path.getsize(os.path.join(current_dir, file)) for file in files)

        formatted_user_dir_size = _format_size(user_dir_size, SCALES[0])

        stat_payload = gloutils.EmailChoicePayload(count=nb_emails, size=formatted_user_dir_size)
        return _success_message(stat_payload)

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
        # TODO : déterminer si envoit est interne ou externe
        # TODO : all the checks and stuff

        if re.search(r"@ulaval.ca?", payload["destination"]):
            message = EmailMessage()
            message["From"] = payload["sender"]
            message["To"] = payload["destination"]
            message["Subject"] = payload["subject"]
            message["Date"] = payload["date"]
            message.set_content(payload["content"])
            try:
                with smtplib.SMTP(host=gloutils.SMTP_SERVER, timeout=10) as connection:
                    connection.send_message(message)
                    return gloutils.GloMessage(header=gloutils.Headers.OK)
            except smtplib.SMTPException:
                return _error_message("Le message n'a pas pu être envoyé.")
            except socket.timeout:
                return _error_message("Le serveur SMTP est injoinable.")

        dir_path = os.path.join(gloutils.SERVER_DATA_DIR, payload["destination"].upper())
        if os.path.exists(dir_path):
            file_path = os.path.join(dir_path, payload["subject"])
            _save(file_path, json.dumps(payload))
            return gloutils.GloMessage(header=gloutils.Headers.OK)

        dir_path = os.path.join(gloutils.SERVER_DATA_DIR, gloutils.SERVER_LOST_DIR)
        file_path = os.path.join(dir_path, payload["subject"])
        _save(file_path, str(payload))
        return _error_message("functionnality was not yet implemented.")


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
                self._send(client_socket, self._get_email(client_socket, payload))
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


def _error_message(message: str) -> gloutils.GloMessage:
    errorPayload = gloutils.ErrorPayload(error_message=message)
    return gloutils.GloMessage(header=gloutils.Headers.ERROR, payload=errorPayload)


def _success_message(payload) -> gloutils.GloMessage:
    return gloutils.GloMessage(header=gloutils.Headers.OK, payload=payload)


def _email_content_payload(email) -> gloutils.EmailContentPayload:
    return gloutils.EmailContentPayload(
        sender=email['sender'],
        destination=email['destination'],
        subject=email['subject'],
        date=email['date'],
        content=email['content']
    )


def _is_username_valid(username: str) -> bool:
    """
    vérifies que le nom d'utilisateur ne contient pas des
    caractères autres que alphanumériques,_, . ou -.
    """
    return re.search(r"[^\w_.-.]", username) is None


def _is_password_valid(password: str) -> bool:
    """
    vérifies que le mot de passe a moins de 10 caractères et
    contient au moins une majuscule, une minuscule et un chiffre
    """
    return len(password) >= 10 and re.search(r"(0-9)?(a-z)?(A-Z)?", password) is not None


def _save_password(path: str, password: str) -> None:
    password_file_path = os.path.join(path, gloutils.PASSWORD_FILENAME)
    _save(password_file_path, _hash_password(password))


def _read_password(path: str) -> str:
    password_file_path = os.path.join(path, gloutils.PASSWORD_FILENAME)
    password_file = open(password_file_path, "r+")
    password = password_file.read()
    password_file.close()
    return password


def _hash_password(password: str) -> str:
    gfg = hashlib.sha3_512()
    gfg.update(password.encode('utf-8'))
    return gfg.hexdigest()


def _save(path: str, data: str) -> None:
    file = open(path, "w+")
    file.write(data)
    file.close()


def _format_size(value: int, scale: str) -> str:
    if scale == SCALES[-1]:
        return f"{value}{scale}"

    if value >= 1024:
        current_scale_index = SCALES.index(scale)
        next_scale = SCALES[current_scale_index + 1]

        new_value = value/1024
        if new_value >= 1024:
            return _format_size(new_value, next_scale)

        return f"{new_value}{next_scale}"

    return f"{value}{scale}"


def _main() -> int:
    server = Server()
    try:
        server.run()
    except KeyboardInterrupt:
        server.cleanup()
    return 0


if __name__ == '__main__':
    sys.exit(_main())
