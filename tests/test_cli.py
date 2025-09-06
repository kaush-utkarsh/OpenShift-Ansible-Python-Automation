from cicd import cli

def test_env_loader(tmp_path):
    envf = tmp_path / ".env"
    envf.write_text("APP_NAME=hello\nNAMESPACE=demo\n")
    vals = cli._load_env_values(str(envf))
    assert vals["APP_NAME"] == "hello"
    assert vals["NAMESPACE"] == "demo"
