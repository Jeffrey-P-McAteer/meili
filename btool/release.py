
import os
import sys
import shutil
import subprocess

# Our libraries

import btool
from . import utils

def main(args=sys.argv):
  btool.main(args)

  linux_release_files = [
    ( os.path.abspath(os.path.join('target', 'x86_64-unknown-linux-gnu', 'release', 'meili-client')), 'linux-x86_64-meili-client'),
    ( os.path.abspath(os.path.join('target', 'x86_64-unknown-linux-gnu', 'release', 'meili-server')), 'linux-x86_64-meili-server'),
    # Todo aarch64 names
  ]

  windows_release_files = [
    ( os.path.abspath(os.path.join('target', 'x86_64-pc-windows-gnu', 'release', 'meili-client.exe')), 'windows-x86_64-meili-client.exe'),
    ( os.path.abspath(os.path.join('target', 'x86_64-pc-windows-gnu', 'release', 'meili-server.exe')), 'windows-x86_64-meili-server.exe' ),
    # Todo aarch64 names
  ]

  macos_release_files = [
    ( os.path.abspath(os.path.join('target', 'Meili.dmg')), 'macos-Meili.dmg'),
    ( os.path.abspath(os.path.join('target', 'x86_64-apple-darwin', 'release', 'meili-client')), 'macos-x86_64-meili-client'),
    ( os.path.abspath(os.path.join('target', 'x86_64-apple-darwin', 'release', 'meili-server')), 'macos-x86_64-meili-server'),
    # Todo aarch64 names
  ]

  asset_staging_dir = os.path.abspath( os.path.join('target', 'release_stage') )
  os.makedirs(asset_staging_dir, exist_ok=True)
  for f in os.listdir(asset_staging_dir):
    os.remove(os.path.join(asset_staging_dir, f))

  assets_to_upload = []
  for file_path, release_name in linux_release_files + windows_release_files + macos_release_files:
    if os.path.exists(file_path):
      release_asset_path = os.path.join(asset_staging_dir, release_name)
      shutil.copy(
        file_path, release_asset_path
      )
      assets_to_upload.append(release_asset_path)

  github_access_token = os.environ.get('GITHUB_ACCESS_TOKEN', '')
  if len(github_access_token) < 1:
    raise Exception('Cannot upload release, GITHUB_ACCESS_TOKEN={}'.format(github_access_token))

  github_username = os.environ.get('GITHUB_USERNAME', '')
  if len(github_username) < 1:
    raise Exception('Cannot upload release, GITHUB_USERNAME={}'.format(github_username))

  git_porcelain_out = subprocess.check_output(['git', 'status', '--porcelain'], stderr=subprocess.STDOUT)
  git_porcelain_out = git_porcelain_out.strip()
  if len(git_porcelain_out) > 2:
    raise Exception('Refusing to release when current directory is not committed! git_porcelain_out={}'.format(git_porcelain_out))

  github_binary_upload = utils.import_maybe_installing_with_pip('github_binary_upload', pkg_name='github-binary-upload')
  toml = utils.import_maybe_installing_with_pip('toml')
  cargo_toml = toml.load('Cargo.toml')
  release_version = cargo_toml.get('package', {}).get('version', '0.0.0')
  release_version = 'v{}'.format(release_version)

  # Create version tag & push to remote, ignoring errors.
  print('Creating tag {}'.format(release_version))
  subprocess.run(['git', 'tag', release_version], check=False)
  subprocess.run(['git', 'push', 'origin', release_version], check=False)

  print('Releasing version {}'.format(release_version))
  for f in assets_to_upload:
    print('> {}'.format(os.path.basename(f)))

  github_binary_upload.publish_release_from_tag(
    '{}/meili'.format(github_username), None, assets_to_upload, 'github.com', github_username, github_access_token, False
  )

  

if __name__ == '__main__':
  main()

