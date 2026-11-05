project('nauta',
  version: '0.1.0',
  meson_version: '>= 1.0',
  license: 'AGPL-3.0-or-later',
)

base_id = 'de.nexumia.Nauta'
# Nightly app next to the stable one (docs/release-channels.md).
nightly = get_option('profile') == 'development'
app_id = nightly ? base_id + '.Devel' : base_id

python = import('python').find_installation('python3')
pythondir = python.get_install_dir()

python.install_sources(
  'nauta/__init__.py',
  'nauta/__main__.py',
  'nauta/actions.py',
  'nauta/api.py',
  'nauta/artist.py',
  'nauta/background.py',
  'nauta/connection.py',
  'nauta/demo.py',
  'nauta/demo_metube.py',
  'nauta/downloads.py',
  'nauta/favourites.py',
  'nauta/find.py',
  'nauta/images.py',
  'nauta/keyring.py',
  'nauta/library.py',
  'nauta/liked.py',
  'nauta/loudness.py',
  'nauta/lyrics.py',
  'nauta/main.py',
  'nauta/metube.py',
  'nauta/mpris.py',
  'nauta/nowplaying.py',
  'nauta/pages.py',
  'nauta/player.py',
  'nauta/player_bar.py',
  'nauta/playlist_edit.py',
  'nauta/preferences.py',
  'nauta/queue_view.py',
  'nauta/resume.py',
  'nauta/settings.py',
  'nauta/setup.py',
  'nauta/sleep.py',
  'nauta/swipe.py',
  'nauta/text.py',
  'nauta/widgets.py',
  'nauta/window.py',
  'nauta/ytmusic.py',
  subdir: 'nauta',
)
# Loaded next to the Python files, also from the source tree.
install_data('nauta/style.css', install_dir: pythondir / 'nauta')

conf = configuration_data()
conf.set('PYTHON', python.full_path())
conf.set('PYTHONDIR', get_option('prefix') / pythondir)
configure_file(
  input: 'data/nauta.in',
  output: 'nauta',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x',
)

config = configuration_data()
config.set('APP_ID', app_id)
config.set('BUILD_LABEL', get_option('build_label'))
configure_file(
  input: 'nauta/config.py.in',
  output: 'config.py',
  configuration: config,
  install: true,
  install_dir: pythondir / 'nauta',
)

if nightly
  # The stable files in data/ stay the only source; the nightly app gets
  # its own id and the name "Nauta (Nightly)".
  sed = find_program('sed')
  variant = [sed, '-e', 's/' + base_id + '/' + app_id + '/g',
             '-e', 's/^Name=Nauta$/Name=Nauta (Nightly)/',
             '-e', 's|<name>Nauta</name>|<name>Nauta (Nightly)</name>|',
             '@INPUT@']
  desktop = configure_file(input: 'data' / base_id + '.desktop',
    output: app_id + '.desktop', command: variant, capture: true)
  metainfo = configure_file(input: 'data' / base_id + '.metainfo.xml',
    output: app_id + '.metainfo.xml', command: variant, capture: true)
else
  desktop = files('data' / base_id + '.desktop')
  metainfo = files('data' / base_id + '.metainfo.xml')
endif
install_data(desktop, install_dir: get_option('datadir') / 'applications')
install_data(metainfo, install_dir: get_option('datadir') / 'metainfo')
install_data('data/icons' / base_id + '.svg',
  install_dir: get_option('datadir') / 'icons/hicolor/scalable/apps',
  rename: app_id + '.svg')

desktop_file_validate = find_program('desktop-file-validate', required: false)
if desktop_file_validate.found()
  test('validate-desktop', desktop_file_validate, args: [desktop])
endif
appstreamcli = find_program('appstreamcli', required: false)
if appstreamcli.found()
  test('validate-metainfo', appstreamcli,
    args: ['validate', '--no-net', metainfo])
endif
