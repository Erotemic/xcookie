import scriptconfig as scfg
from typing import Any


class XCookieConfig(scfg.Config):
    default: Any

    def normalize(self) -> None:
        ...

    def confirm(self, msg: str, default: bool = True) -> bool:
        ...

    @classmethod
    def main(cls, cmdline: int = ..., **kwargs) -> None:
        ...


class TemplateApplier:
    config: Any
    repodir: Any
    repo_name: Any
    template_infos: Any
    template_dpath: Any
    staging_dpath: Any

    def __init__(self, config) -> None:
        ...

    def setup(self):
        ...

    def copy_staged_files(self) -> None:
        ...

    def vcs_checks(self) -> None:
        ...

    def apply(self) -> None:
        ...

    def lut(self, info) -> str:
        ...

    staging_infos: Any

    def stage_files(self) -> None:
        ...

    def gather_tasks(self):
        ...

    def build_pyproject(self) -> str:
        ...

    def rotate_secrets(self) -> None:
        ...


def main() -> None:
    ...
