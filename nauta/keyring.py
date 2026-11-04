"""Password and certificate password in the keyring (phosh_toolkit
keyring: libsecret, in the Flatpak through the Secret portal).
NAUTA_KEYRING=memory keeps them in memory only, for tests and
screenshots."""
from phosh_toolkit.keyring import CERTIFICATE_PASSWORD, Keyring

# Subsonic's token authentication needs the password itself
# (docs/connection.md).
PASSWORD = "password"

KEYRING = Keyring("de.nexumia.Nauta",
                  {PASSWORD: "Nauta server password",
                   CERTIFICATE_PASSWORD: "Nauta client certificate password"},
                  memory_env="NAUTA_KEYRING")
store = KEYRING.store
lookup = KEYRING.lookup
clear = KEYRING.clear
