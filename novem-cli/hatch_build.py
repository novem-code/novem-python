"""Turn a prebuilt novem release binary into a platform wheel.

Required environment:
  NOVEM_CLI_VERSION  release version, e.g. 0.2.2
  NOVEM_CLI_TARGET   rust target triple the binary was built for
  NOVEM_CLI_BINARY   absolute path to that binary (the build runs in novem-cli/)
"""

import os
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

# rust target -> wheel platform tag. The linux binaries are static musl, so
# they run on both glibc and musl distros.
PLATFORM_TAGS = {
    "x86_64-unknown-linux-musl": "manylinux_2_17_x86_64.manylinux2014_x86_64.musllinux_1_1_x86_64",
    "aarch64-unknown-linux-musl": "manylinux_2_17_aarch64.manylinux2014_aarch64.musllinux_1_1_aarch64",
    "aarch64-apple-darwin": "macosx_11_0_arm64",
    # rust's default deployment target for Intel macOS
    "x86_64-apple-darwin": "macosx_10_12_x86_64",
    "x86_64-pc-windows-msvc": "win_amd64",
}


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        if self.target_name != "wheel":
            raise RuntimeError("novem-cli only ships platform wheels")

        target = os.environ["NOVEM_CLI_TARGET"]
        binary = os.environ["NOVEM_CLI_BINARY"]
        if target not in PLATFORM_TAGS:
            raise RuntimeError(f"unsupported target {target!r}, expected one of {sorted(PLATFORM_TAGS)}")

        # hatchling copies the source file mode into the wheel, and release
        # downloads come without the executable bit
        os.chmod(binary, 0o755)

        name = "novem.exe" if "windows" in target else "novem"
        build_data["force_include"][binary] = f"novem_cli/bin/{name}"
        build_data["tag"] = f"py3-none-{PLATFORM_TAGS[target]}"
        build_data["pure_python"] = False
