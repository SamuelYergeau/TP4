"""\
GLO-2000 Travail pratique 4 - Client
Noms et numéros étudiants:
-
-
-
"""

import argparse
import socket
import sys

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
        self._socket = self._make_client_socket("127.0.0.1", gloutils.APP_PORT)
        self._username = None

    def _make_client_socket(self, destination: str, port: int) -> socket.socket:
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
        payload = self._get_credentials()
        response = self._send(gloutils.Headers.AUTH_REGISTER, payload)
        
        if response.header == gloutils.Headers.OK:
            self._username = payload.username
        else:
            print(response.payload)

    def _login(self) -> None:
        """
        Demande un nom d'utilisateur et un mot de passe et les transmet au
        serveur avec l'entête `AUTH_LOGIN`.

        Si la connexion est effectuée avec succès, l'attribut `_username`
        est mis à jour, sinon l'erreur est affichée.
        """
        payload = self._get_credentials()
        response = self._send(gloutils.Headers.AUTH_LOGIN, payload)

        if response.header == gloutils.Headers.OK:
            self._username = payload.username
        else:
            print(response.payload)

    def _get_credentials(self) -> gloutils.AuthPayload:
        user_name = input("userName : ")
        password = input("password : ")

        return gloutils.AuthPayload(username=user_name, password=password)

    def _quit(self) -> None:
        """
        Préviens le serveur de la déconnexion avec l'entête `BYE` et ferme le
        socket du client.
        """
        self._send(gloutils.Headers.BYE)
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
        response = self._send(gloutils.Headers.INBOX_READING_REQUEST)
        if response.header == gloutils.Headers.OK:
            emails = gloutils.EmailListPayload(response.payload)

            if len(emails) == 0:
                print("there is no emails in your inbox")
                return

            choice = self._get_inbox_reading_choice(emails)
            self._read_selected_email(choice)
        else:
            print(response.payload)

    def _get_inbox_reading_choice(self, emails: list[str]) -> int:
        """
        shows the list of emails to the user and asks them what email they want to read
        """
        print("Emails in inbox")
        for id, email in enumerate(emails):
            print(f"{id} : {email}")

        choice = input("enter the number of the email you would like to consult")
        return choice # TODO : ajouter vérificaton que c'est bien dans la liste

    def _read_selected_email(self, email_id: int) -> None:
        """
        get the selected email from the server and displays it
        """
        payload = gloutils.EmailChoicePayload(email_id)
        response = self._send(gloutils.Headers.INBOX_READING_CHOICE, payload)

        if response.header == gloutils.Headers.OK:
            email = gloutils.EmailContentPayload(response.payload)
            print(_email_display(email))
        else:
            print(response.payload)

    def _send_email(self) -> None:
        """
        Demande à l'utilisateur respectivement:
        - l'adresse email du destinataire,
        - le sujet du message,
        - le corps du message.

        La saisie du corps se termine par un point seul sur une ligne.

        Transmet ces informations avec l'entête `EMAIL_SENDING`.
        """

    def _check_stats(self) -> None:
        """
        Demande les statistiques au serveur avec l'entête `STATS_REQUEST`.

        Affiche les statistiques à l'aide du gabarit `STATS_DISPLAY`.
        """
        response = self._send(gloutils.Headers.STATS_REQUEST)

        if response.header == gloutils.Headers.OK:
            stats = gloutils.StatsPayload(response.payload)
            print(_stats_display(stats))
        else:
            print(response.payload)


    def _logout(self) -> None:
        """
        Préviens le serveur avec l'entête `AUTH_LOGOUT`.

        Met à jour l'attribut `_username`.
        """
        response = self._send(gloutils.Headers.AUTH_LOGOUT)

        if gloutils.Headers(response) == gloutils.Headers.OK:
            self._username = None
        else:
            print(response.payload)


    def _send(self, header, payload):
        """
        abstracts the encapsulation, communication and checks for errors and stuff
        TODO : I guess some verifications or something
        """
        message = gloutils.GloMessage(
            header=header,
            payload=payload
        )

        glosocket.send_msg(self._socket, message)
        response = gloutils.GloMessage(glosocket.recv_msg(self._socket))

        return response

    def run(self) -> None:
        """Point d'entrée du client."""
        should_quit = False

        while not should_quit:
            if not self._username:
                # Authentication menu
                pass
            else:
                # Main menu
                pass


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--destination", action="store",
                        dest="dest", required=True,
                        help="Adresse IP/URL du serveur.")
    args = parser.parse_args(sys.argv[1:])
    client = Client(args.dest)
    client.run()
    return 0


def _email_display(email: gloutils.EmailContentPayload) -> str:
    return gloutils.EMAIL_DISPLAY(
        sender=email.sender,
        to=email.destination,
        subject=email.subject,
        date=email.date,
        body=email.content
    )


def _stats_display(stats: gloutils.StatsPayload) -> str:
    return gloutils.STATS_DISPLAY(
        count=stats.count,
        size=stats.size
    )


if __name__ == '__main__':
    sys.exit(_main())
