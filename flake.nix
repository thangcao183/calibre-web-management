{
  description = "Python development shell";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
      python = pkgs.python312;
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        packages = [
          python
          python.pkgs.pip
          python.pkgs.virtualenv
          pkgs.git
          pkgs.zsh
        ];

        shellHook = ''
          export VENV_DIR=.venv

          if [ ! -d "$VENV_DIR" ]; then
            python -m venv "$VENV_DIR"
          fi

          source "$VENV_DIR/bin/activate"

          echo "Python dev shell activated"
          echo "Python: $(python --version)"
        '';
      };
    };
}