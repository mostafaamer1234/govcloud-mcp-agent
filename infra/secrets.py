from __future__ import annotations

import os


class KmsLikeSecrets:
    """
    Demo-only secrets wrapper.
    In GovCloud you'd use KMS + Secrets Manager / Parameter Store + IAM.
    """

    @staticmethod
    def get(name: str) -> str:
        val = os.getenv(name)
        if val is None:
            raise KeyError(f"Missing secret env var: {name}")
        return val