{
  description = "Novem flake";

  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";
    poetry2nix = {
      url = "github:nix-community/poetry2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, flake-utils, ... }@inputs:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        # Use `inputs` to avoid shadowing + infinite recursion
        poetry2nix = inputs.poetry2nix.lib.mkPoetry2Nix { inherit pkgs; };
        poetryEnv = poetry2nix.mkPoetryEnv {
          projectDir = ./.;
          preferWheels = true;
          # groups = [];
          # checkGroups = [];
        };
      in {
        checks = {
          default = pkgs.runCommand "run-pytest" { } ''
            ${poetryEnv}/bin/pytest ${self}
            touch $out
          '';
        };

        packages = {
          # Main Novem Python app/package
          novem = poetry2nix.mkPoetryApplication {
            projectDir = ./.;
            preferWheels = true;
          };
          poetryEnv = poetryEnv;
          default = self.packages.${system}.novem;
        };

        # Development env
        # Enter using `nix develop` (or using `direnv`)
        devShells.default = poetryEnv.env;
      });
}
