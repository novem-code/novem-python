{
  description = "Novem flake";

  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, flake-utils, pyproject-nix, uv2nix, pyproject-build-systems, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python312;

        # Load workspace from uv.lock
        workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

        # Create package overlay from workspace
        overlay = workspace.mkPyprojectOverlay {
          sourcePreference = "wheel";
        };

        # Build Python package set
        pyprojectOverrides = _final: _prev: {
          # Add any package-specific overrides here if needed
        };

        pythonSet =
          (pkgs.callPackage pyproject-nix.build.packages {
            inherit python;
          }).overrideScope
            (
              pkgs.lib.composeManyExtensions [
                pyproject-build-systems.overlays.default
                overlay
                pyprojectOverrides
              ]
            );

        # Virtual environment for development (with dev dependencies)
        venv = pythonSet.mkVirtualEnv "novem-dev-env" workspace.deps.all;

        # Virtual environment for development (with dev dependencies)
        venvProd = pythonSet.mkVirtualEnv "novem-env" workspace.deps.default;

        # Standalone novem package with just the CLI script
        novemApp = pkgs.runCommand "novem" {
          nativeBuildInputs = [ pkgs.makeWrapper ];
        } ''
          mkdir -p $out/bin
          makeWrapper ${venvProd}/bin/novem $out/bin/novem
        '';

      in {
        checks = {
          default = pkgs.runCommand "run-pytest" { } ''
            ${venv}/bin/pytest ${self}
            touch $out
          '';
        };

        packages = {
          # Main Novem Python CLI app
          novem = novemApp;
          default = self.packages.${system}.novem;
          # Full virtual environments
          venv = venv;
          venvProd = venvProd;
        };

        # Development env
        # Enter using `nix develop` (or using `direnv`)
        devShells.default = pkgs.mkShell {
          packages = [
            venv
            pkgs.uv
          ];
        };
      });
}
