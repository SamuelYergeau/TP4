"""\
GLO-2000 Travail pratique 4 - Client
Noms et numéros étudiants:
-
-
-
"""

import argparse
import json
import socket
import sys
from getpass import getpass

import glosocket
import gloutils


class Client:
    """Client pour le serveur mail @glo2000.ca."""

    def __init__(self, destination: str) -> None:
        """
        Prépare et connecte le socket du client `_socket`.

        Prépare un attribut `_username` pour stocker le nom d'utilisateur
        courant. Laissé vide quand l'utilisateur n'est pas connecté.
        """
        self._socket = self._make_client_socket(destination, gloutils.APP_PORT)
        self._username = None

    @staticmethod
    def _make_client_socket(destination: str, port: int) -> socket.socket:
        """ setup for the client socket """
        try:
            client_soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_soc.connect((destination, port))
            return client_soc
        except glosocket.GLOSocketError:
            sys.exit(-1)

    def _register(self) -> None:
        """
        Demande un nom d'utilisateur et un mot de passe et les transmet au
        serveur avec l'entête `AUTH_REGISTER`.

        Si la création du compte s'est effectuée avec succès, l'attribut
        `_username` est mis à jour, sinon l'erreur est affichée.
        """
        payload: gloutils.AuthPayload = self._get_credentials()
        response = self._send_receive(gloutils.Headers.AUTH_REGISTER, payload)

        if self._is_response_ok(response):
            self._username = payload["username"]

    def _login(self) -> None:
        """
        Demande un nom d'utilisateur et un mot de passe et les transmet au
        serveur avec l'entête `AUTH_LOGIN`.

        Si la connexion est effectuée avec succès, l'attribut `_username`
        est mis à jour, sinon l'erreur est affichée.
        """
        payload: gloutils.AuthPayload = self._get_credentials()
        response = self._send_receive(gloutils.Headers.AUTH_LOGIN, payload)

        if self._is_response_ok(response):
            self._username = payload["username"]

    @staticmethod
    def _get_credentials() -> gloutils.AuthPayload:
        user_name = input("userName : ")
        password = getpass("password : ")

        return gloutils.AuthPayload(username=user_name, password=password)

    def _quit(self) -> None:
        """
        Préviens le serveur de la déconnexion avec l'entête `BYE` et ferme le
        socket du client.
        """
        message = gloutils.GloMessage(header=gloutils.Headers.BYE)
        glosocket.send_msg(self._socket, json.dumps(message))
        self._socket.close()

    def _read_email(self) -> None:
        """
        Demande au serveur la liste de ses courriels avec l'entête
        `INBOX_READING_REQUEST`.

        Affiche la liste des courriels puis transmet le choix de l'utilisateur
        avec l'entête `INBOX_READING_CHOICE`.

        Affiche le courriel à l'aide du gabarit `EMAIL_DISPLAY`.

        S'il n'y a pas de courriel à lire, l'utilisateur est averti avant de
        retourner au menu principal.
        """
        response = self._send_receive(gloutils.Headers.INBOX_READING_REQUEST)
        if self._is_response_ok(response):
            emails = self._get_email_list_from_payload(response)
            if emails:
                self._selected_email(emails)

    @staticmethod
    def _get_email_list_from_payload(response: dict) -> list[str]:
        response_payload = response["payload"]
        emails = response_payload["email_list"]

        if len(emails) == 0:
            print("there is no emails in your inbox")
            return None

        return emails

    def _selected_email(self, emails: list[str]) -> None:
        """
        get the selected email from the server and displays it
        """
        email_id = self._get_inbox_reading_choice(emails)

        payload = gloutils.EmailChoicePayload(choice=email_id)
        response = self._send_receive(gloutils.Headers.INBOX_READING_CHOICE, payload)

        if self._is_response_ok(response):
            print(f"\n{_payload_to_email(response['payload'])}")

    def _get_inbox_reading_choice(self, emails: list[str]) -> int:
        """
        shows the list of emails to the user and asks them what email they want to read
        """
        print("\nEmails in inbox")
        for email in emails:
            print(f"{email}")

        choice = input("enter the number of the email you would like to consult\n")

        if choice not in range(1, len(emails)):
            print(f"\n'{choice}' ne correspond pas au numéro d'un courriel listé.")
            return self._get_inbox_reading_choice(emails)

        return choice

    def _send_email(self) -> None:
        """
        Demande à l'utilisateur respectivement:
        - l'adresse email du destinataire,
        - le sujet du message,
        - le corps du message.

        La saisie du corps se termine par un point seul sur une ligne.

        Transmet ces informations avec l'entête `EMAIL_SENDING`.
        """

        payload = self._make_email_content_payload()
        response = self._send_receive(gloutils.Headers.EMAIL_SENDING, payload)

        if self._is_response_ok(response):
            print("\nemail was sent sucessfully")

    def _make_email_content_payload(self) -> gloutils.EmailContentPayload:
        dest, sub, body = self._get_email_infos()

        return gloutils.EmailContentPayload(
            sender=f"{self._username}.{gloutils.SERVER_DOMAIN}",
            destination=dest,
            subject=sub,
            date=gloutils.get_current_utc_time(),
            content=body
        )

    @staticmethod
    def _get_email_infos() -> (str, str, str):
        """
        asks the user for the informations necessary for the email
        """
        dest: str = input("adresse email du destinataire : ")
        subject: str = input("sujet du message : ")
        body: str = input("corps du message : ")

        return dest, subject, body

    def _check_stats(self) -> None:
        """
        Demande les statistiques au serveur avec l'entête `STATS_REQUEST`.

        Affiche les statistiques à l'aide du gabarit `STATS_DISPLAY`.
        """
        response = self._send_receive(gloutils.Headers.STATS_REQUEST)

        if self._is_response_ok(response):
            print(f"\n{_payload_to_stats(response['payload'])}")

    def _logout(self) -> None:
        """
        Préviens le serveur avec l'entête `AUTH_LOGOUT`.

        Met à jour l'attribut `_username`.
        """
        message = gloutils.GloMessage(header=gloutils.Headers.AUTH_LOGOUT)
        glosocket.send_msg(self._socket, json.dumps(message))
        self._username = None

    def _send_receive(self, header, payload=None):
        """
        abstracts the encapsulation, communication and checks for errors and stuff
        """
        if payload:
            self._send(header, payload)
        else:
            message = gloutils.GloMessage(header=header)
            glosocket.send_msg(self._socket, json.dumps(message))

        response = glosocket.recv_msg(self._socket)

        return json.loads(response)

    def _send(self, header, payload) -> None:
        message = gloutils.GloMessage(
            header=header,
            payload=payload
        )

        glosocket.send_msg(self._socket, json.dumps(message))

    @staticmethod
    def _is_response_ok(response: dict) -> bool:
        if response["header"] == gloutils.Headers.OK:
            return True
        elif response["header"] == gloutils.Headers.ERROR:
            payload = response["payload"]
            print(f"\nERROR : {payload['error_message']}")
            return False
        else:
            print(f"\nERROR : server's message was not recognised")
            return False

    def run(self) -> None:
        """Point d'entrée du client."""
        should_quit = False

        while not should_quit:
            if not self._username:
                action = input(f"\n{gloutils.CLIENT_AUTH_CHOICE}\n")

                match int(action):
                    case 1:
                        self._register()
                    case 2:
                        self._login()
                    case 3:
                        self._quit()
                        should_quit = True
                    case _:
                        print("La valeur entrée ne corresponds pas à une des options listées")
            else:
                action = input(f"\n{gloutils.CLIENT_USE_CHOICE}\n")

                match int(action):
                    case 1:
                        self._read_email()
                    case 2:
                        self._send_email()
                    case 3:
                        self._check_stats()
                    case 4:
                        self._logout()
                    case _:
                        print("La valeur entrée ne corresponds pas à une des options listées")


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--destination", action="store",
                        dest="dest", required=True,
                        help="Adresse IP/URL du serveur.")
    args = parser.parse_args(sys.argv[1:])
    client = Client(args.dest)
    client.run()
    return 0


def _payload_to_stats(stats: dict) -> gloutils.StatsPayload:
    return gloutils.STATS_DISPLAY.format(
        count=stats["count"],
        size=stats["size"]
    )


def _payload_to_email(email: gloutils.EmailContentPayload) -> str:
    return gloutils.EMAIL_DISPLAY.format(
        sender=email["sender"],
        to=email["destination"],
        subject=email["subject"],
        date=email["date"],
        body=email["content"]
    )


if __name__ == '__main__':
    sys.exit(_main())
