"""Generate a throwaway CA plus server and client certificates for local mTLS.

Certificates are created at setup time and are git-ignored; private keys never
belong in the repository. In production these come from ACM Private CA.

    python scripts/gen_certs.py --out certs
"""

from __future__ import annotations

import argparse
import datetime as dt
import ipaddress
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def _key() -> ec.EllipticCurvePrivateKey:
    return ec.generate_private_key(ec.SECP256R1())


def _write(path: Path, key: ec.EllipticCurvePrivateKey, cert: x509.Certificate) -> None:
    path.with_suffix(".key").write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    path.with_suffix(".crt").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    path.with_suffix(".key").chmod(0o600)


def _name(cn: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME, "govcloud-mcp-agent"), x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def make_ca(cn: str) -> tuple[ec.EllipticCurvePrivateKey, x509.Certificate]:
    key, now = _key(), dt.datetime.now(dt.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(_name(cn))
        .issuer_name(_name(cn))
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
        .sign(key, hashes.SHA256())
    )
    return key, cert


def make_leaf(cn: str, ca_key: ec.EllipticCurvePrivateKey, ca_cert: x509.Certificate, *, server: bool) -> tuple[ec.EllipticCurvePrivateKey, x509.Certificate]:
    key, now = _key(), dt.datetime.now(dt.UTC)
    builder = (
        x509.CertificateBuilder()
        .subject_name(_name(cn))
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=7))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH if server else ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
    )
    if server:
        builder = builder.add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost"), x509.DNSName("mcp-server"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
            critical=False,
        )
    return key, builder.sign(ca_key, hashes.SHA256())


def generate(out: str | Path, client_cn: str = "research-agent") -> Path:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    ca_key, ca_cert = make_ca("govcloud-mcp-agent local CA")
    _write(out / "ca", ca_key, ca_cert)
    _write(out / "server", *make_leaf("localhost", ca_key, ca_cert, server=True))
    _write(out / "client", *make_leaf(client_cn, ca_key, ca_cert, server=False))
    # A client signed by an unrelated CA, used by tests to prove untrusted certs are rejected.
    rogue_key, rogue_cert = make_ca("untrusted CA")
    _write(out / "rogue_client", *make_leaf("rogue-agent", rogue_key, rogue_cert, server=False))
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="certs")
    parser.add_argument("--client-cn", default="research-agent")
    args = parser.parse_args()
    print(f"wrote certificates to {generate(args.out, args.client_cn)}")
