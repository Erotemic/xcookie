__doc__="
This script shows how I create new repos.
"

make_kitware_repo(){

    load_secrets
    HOST=https://gitlab.kitware.com
    PRIVATE_GITLAB_TOKEN="$(git_token_for "$HOST")"
    export PRIVATE_GITLAB_TOKEN

    python -m xcookie.main --repodir="$HOME"/code/kwgis --tags="kitware,gitlab,purepy,cv2,gdal"

    load_secrets
    HOST=https://gitlab.kitware.com
    PRIVATE_GITLAB_TOKEN="$(git_token_for "$HOST")"
    export PRIVATE_GITLAB_TOKEN
    cd /home/joncrall/code/kwgis
    source /home/joncrall/code/kwgis/dev/setup_secrets.sh

    # FIXME: portable solution
    permit_erotemic_gitrepo

    setup_package_environs_gitlab_kitware
    export_encrypted_code_signing_keys
    upload_gitlab_repo_secrets

    cd /home/joncrall/code/kwgis

    xdev sed watch kwgis
}
