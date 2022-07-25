#!/usr/bin/env python3

from fabric import Connection
from fabric import Config
import getpass
from paramiko.ssh_exception import AuthenticationException
from paramiko.ssh_exception import NoValidConnectionsError
from invoke import Responder
import tomli

def setup_react_project(
    conn, repo_uri, 
    repo_user,
    repo_password,
    project_name,
    path_to_download="$HOME"
):
    """
    Setup a React project on a remote host.
    """

    # Downloading the project
    repo_user = Responder(
        pattern=r"Username for (.)*",
        response=f"{repo_user}\n"
    )
    repo_password = Responder(
        pattern=r"Password for (.)*",
        response=f"{repo_password}\n"
    )
    conn.run(f"mkdir -p {path_to_download}")
    with conn.cd(path_to_download):
        conn.run(f"git clone {repo_uri}", pty=True, watchers=[repo_password, repo_user])
    
    # compiling the project
    project_path = f"{path_to_download}/{project_name}"
    with conn.cd(project_path):
        conn.run("npm install --save-exact")
        conn.run("npm run build")
    return project_path

def configure_git(conn, project_path, user="Fabric", email=""):
    """
    Configure Git on a remote host.
    """
    with conn.cd(project_path):
        conn.run(f"git config --global --add safe.directory {project_path}")
        conn.run(f"git config user.name '{user}'")
        conn.run(f"git config user.email '{email}'")

def push_compiled_project_files(conn, project_path, repo_user, repo_password):
    """
    Push the project to the remote host.
    """
    repo_user = Responder(
        pattern=r"Username for (.)*",
        response=f"{repo_user}\n"
    )
    repo_password = Responder(
        pattern=r"Password for (.)*",
        response=f"{repo_password}\n"
    )
    with conn.cd(project_path):
        conn.run("git add -f build/*")
        conn.run("git commit -m 'compiled project'")
        conn.run("git push", pty=True, watchers=[repo_password, repo_user])

def install_packages(conn, package):
    """
    Install a packages on a remote host.
    """
    conn.sudo("apt upgrade")
    conn.sudo(f"sudo apt install -y {package}")

def install_nodejs(conn, version="14.x"):
    """
    Install NodeJS 14.x on a remote host.
    """
    conn.sudo(f"curl -sL https://deb.nodesource.com/setup_{version} | sudo -E bash -")
    conn.sudo("sudo apt install -y nodejs")

if __name__ == "__main__":

    with open("fab.conf", "rb") as f:
        fab_conf = tomli.load(f)

    server_user_password = getpass.getpass("Enter the user password: ")
    gitlab_password = getpass.getpass("Enter the gitlab password: ")

    config = Config(overrides={'sudo': {'password': server_user_password}})

    try:
        with Connection(
            host=fab_conf['server_credencials']["host"], 
            user=fab_conf['server_credencials']["username"],
            port=fab_conf['server_credencials']["port"],
            connect_kwargs={"password": server_user_password},
            config=config
        ) as conn:
            apt_packages = " ".join(fab_conf["packages"]["apt_packages"])
            install_packages(conn, apt_packages)
            install_nodejs(conn, fab_conf["packages"]["nodejs_version"])
            project_path = setup_react_project(
                conn, 
                fab_conf["git"]["gitlab"]["repo_uri"],
                fab_conf["git"]["gitlab"]["username"],
                gitlab_password,
                fab_conf["project"]["name"],
                fab_conf["project"]["path_to_download"]
            )
            configure_git(
                conn, project_path, 
                fab_conf["git"]["git"]["config_name"], 
                fab_conf["git"]["git"]["config_email"], 
            )
            push_compiled_project_files(
                conn, project_path, 
                fab_conf["git"]["gitlab"]["username"],
                gitlab_password
            )
    except AuthenticationException as e:
        print("Authentication failed. Please check your credentials.")
    except NoValidConnectionsError as e:
        print("Could not connect to the specified host.")
    except Exception as e:
        print(e)