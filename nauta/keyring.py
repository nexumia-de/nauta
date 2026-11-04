"""Password and certificate password in the keyring (phosh_toolkit
keyring: libsecret, in the Flatpak through the Secret portal).
NAUTA_KEYRING=memory keeps them in memory only, for tests and
screenshots."""
from phosh_toolkit.keyring import CERTIFICATE_PASSWORD, Keyring
from phosh_toolkit.proxy_login import COOKIES

# Subsonic's token authentication needs the password itself
# (docs/connection.md).
PASSWORD = "password"

KEYRING = Keyring("de.nexumia.Nauta",
                  {PASSWORD: "Nauta server password",
                   CERTIFICATE_PASSWORD: "Nauta client certificate password"},
                  memory_env="NAUTA_KEYRING")
# The download server (MeTube, docs/downloads.md) has its own client
# certificate and proxy login; a schema of its own keeps them apart from
# the music server's.
DOWNLOADS = Keyring("de.nexumia.Nauta.Downloads",
                    {CERTIFICATE_PASSWORD: "Nauta download server certificate password",
                     COOKIES: "Nauta download server proxy login"},
                    memory_env="NAUTA_KEYRING")
store = KEYRING.store
lookup = KEYRING.lookup
clear = KEYRING.clear
