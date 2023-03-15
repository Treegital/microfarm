import io
import orjson
import typing as t
from branding_iron import keys, pki, certificate
from branding_iron.identity import Identity
from bundle import PKI
from utils import data_from_file, data_to_file


def create_root_certificate(settings):
    identity = Identity(**settings.identity)
    private_key = keys.new_ed448_key()

    startdate = certificate.validity_start()
    enddate = certificate.validity_end(startdate, delta=3650)  # 10 years

    cert = pki.create_root_ca_cert(
        identity,
        private_key,
        startdate=startdate,
        enddate=enddate
    )
    return cert, private_key


def create_intermediate_certificate(settings, issuer_cert, issuer_key):
    identity = Identity(**settings.identity)
    private_key = keys.new_ed25519_key()
    startdate = certificate.validity_start()
    enddate = certificate.validity_end(startdate, delta=1095)  # 3 years
    cert = pki.create_intermediate_ca_cert(
        identity,
        issuer_cert_subject=issuer_cert.subject,
        issuer_key=issuer_key,
        startdate=startdate,
        enddate=enddate,
        intermediate_private_key=private_key
    )
    return cert, private_key


def create_pki(debug: bool = False):
    import dynaconf

    settings = dynaconf.Dynaconf(settings_files=["pki.toml"])

    if root_pem := data_from_file(settings.pki.root.cert_path):
        root = certificate.pem_decrypt_x509(root_pem)
    else:
        root = None

    if inter_pem := data_from_file(settings.pki.intermediate.cert_path):
        inter = certificate.pem_decrypt_x509(inter_pem)
    else:
        inter = None

    if inter is None:
        if root_key_pem := data_from_file(settings.pki.root.key_path):
            root_key = keys.pem_decrypt_key(
                root_key_pem,
                settings.pki.root.password.encode()
            )
        else:
            root_key = None

        if (root is None) ^ (root_key is None):
            raise ValueError(
                'To generate an intermediate certificate, '
                'you need the root cert and the root private key'
            )
        elif root is None and root_key is None:
            print('Creating root')
            root, root_key = create_root_certificate(settings.pki.root)
            data_to_file(
                settings.pki.root.cert_path,
                certificate.pem_encrypt_x509(root)
            )
            data_to_file(
                settings.pki.root.key_path,
                keys.pem_encrypt_key(
                    root_key,
                    settings.pki.root.password.encode()
                )
            )

        print('Creating intermediate')
        inter, inter_key = create_intermediate_certificate(
            settings.pki.intermediate,
            root,
            root_key
        )
        data_to_file(
            settings.pki.intermediate.cert_path,
            certificate.pem_encrypt_x509(inter)
        )
        data_to_file(
            settings.pki.intermediate.key_path,
            keys.pem_encrypt_key(
                inter_key,
                settings.pki.intermediate.password.encode()
            )
        )

    elif root is None:
        raise NotImplementedError('PKI misses the root certificate.')
    else:
        if inter_key_pem := data_from_file(settings.pki.intermediate.key_path):
            inter_key = keys.pem_decrypt_key(
                inter_key_pem,
                settings.pki.intermediate.password.encode()
            )
        else:
            raise NotImplementedError(
                'PKI misses the intermediate private key.')
        # here, verify that the root is the issuer of intermediate

    return PKI(inter, inter_key, [root])
