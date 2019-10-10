with import <nixpkgs> {};
with python27Packages;

buildPythonPackage rec {
  name = "mypackage";
  src = ./sphinx_multibuild;
  propagatedBuildInputs = [ setuptools wheel watchdog sphinx ];
}
