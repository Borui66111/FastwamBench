# Pushing fastwam_bench to a remote

The local repository is **ready**: one commit on `main`, 54 tracked files, 596 KB, no file over 40 KB.
The ~83 GB of downloaded payloads are gitignored and re-fetched by the scripts. Nothing is left to do
locally.

The remote push is **blocked on credentials**, verified on this machine:

| check | result |
|---|---|
| `git push --dry-run` to `DeepSota/MobileJail` (existing repo) | `Permission to DeepSota/MobileJail.git denied to Borui66111` — HTTP 403 |
| `git ls-remote` `DeepSota/MobileJail` | works (read) |
| `DeepSota/fastwam_bench` | does not exist yet (`remote: Repository not found`) |
| `gh` CLI | not installed |
| SSH keys | none (`~/.ssh` absent) |
| credential source | VS Code askpass shim (`GIT_ASKPASS=.../vscode-git-*.sh`), account **Borui66111** |

The account that the VS Code login authenticates as is **Borui66111**, which has no write access to the
`DeepSota` organization. Pushing therefore needs either a different account/token, or a repo under an
owner that `Borui66111` can write to.

`origin` is already configured as `https://github.com/DeepSota/fastwam_bench.git` — change it if you
pick a different owner:

```bash
git -C /data1/liborui/fastwam_bench remote set-url origin <your-repo-url>
```

## Option A — gh CLI (easiest; creates the repo and pushes)

```bash
# install (no root needed)
mkdir -p ~/.local/bin
curl -sL https://github.com/cli/cli/releases/download/v2.62.0/gh_2.62.0_linux_amd64.tar.gz \
  | tar xz -C /tmp
cp /tmp/gh_2.62.0_linux_amd64/bin/gh ~/.local/bin/
export PATH="$HOME/.local/bin:$PATH"

gh auth login          # log in as an account with write access to the target org
cd /data1/liborui/fastwam_bench
gh repo create <owner>/fastwam_bench --private --source=. --remote=origin --push
```

## Option B — create the repo in the web UI, then push

Create an **empty** repo (no README, no .gitignore, no license) at the host of your choice, then:

```bash
cd /data1/liborui/fastwam_bench
git push -u origin main
```

If the push prompts for credentials and the VS Code askpass cannot supply them (it fails with
`ECONNREFUSED /run/user/1014/vscode-git-*.sock` when run outside VS Code's terminal), use a token:

```bash
# token is used for this one command and is NOT written to .git/config
git push https://<user>:<token>@github.com/<owner>/fastwam_bench.git main
```

Then clear it from the remote so it is not persisted:

```bash
git -C /data1/liborui/fastwam_bench remote set-url origin https://github.com/<owner>/fastwam_bench.git
```

## Visibility note

`server_notes/` documents the internal machine (hostname, GPU and disk inventory). If the repo will be
**public**, consider dropping it from the commit before pushing:

```bash
git -C /data1/liborui/fastwam_bench rm -r --cached server_notes
echo 'server_notes/' >> /data1/liborui/fastwam_bench/.gitignore
git -C /data1/liborui/fastwam_bench commit --amend --no-edit
```

No credentials, tokens or private keys were found in the tracked content (scanned before committing).
