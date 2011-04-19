
CONFIG_DEFAULTS = """\
[jurt]
default-target = undefined
log-format = $(levelname)s: $(message)s

[conf]
path-environment = JURT_CONF
user-file = .jurt.conf
system-file = /etc/jurt/jurt.conf

#
# configuration options valid for "any target", which can be overriden in
# [target] sections
#
[any target]

arch = host
arch-map = i586 /usr/bin/setarch i586

root-type = chroot-with-cache
base-packages = basesystem-minimal rpm-build rpm-mandriva-setup urpmi rsync
                bzip2
pm-type = urpmi
build-type = default
su-type = jurt-root-wrapper
logger-type = default

jurt-base-dir = /var/spool/jurt
roots-path = %(jurt-base-dir)s/chroots/
builds-dir = %(jurt-base-dir)s/builds/
spool-dir = %(builds-dir)s/spools/
logs-dir = %(builds-dir)s/logs/
failure-dir = %(builds-dir)s/fail/
success-dir = %(builds-dir)s/success/

build-user = builder
builder-home = /home/$username
builder-uid = 65555
builder-uid-doc = note the builder-uid option is not used when using
                  jurt-shell or jurt-build --stop
chroot-spool-dir = /build-spool/
built-dir-name = packages
delivery-dir = ~/jurt/
delivery-log-file-ext = .xz
log-compress-command = xz -9c
logs-dir-name = logs
latest-link-name = latest
packages-dir-name = packages
chroot-compress-command = tar czf
chroot-decompress-command = tar xzf
chroot-cache-ext = .tar.gz
chroot-cache-dir = %(jurt-base-dir)s/chroots/cached/
buildid-timefmt = %Y.%m.%d.%H%M%S

sudo-command = /usr/bin/sudo -n
jurt-root-command-command = /usr/sbin/jurt-root-command
command-poll-time = 0.5

urpmi-command = /usr/bin/env -i /usr/sbin/urpmi
urpmiaddmedia-command = /usr/sbin/urpmi.addmedia --no-md5sum
urpmi-extra-options = --no-suggests --excludedocs
urpmi-update-command = /usr/sbin/urpmi.update -a
urpmi-valid-options = root= auto no-suggests excludedocs auto-select proxy=
                      use-distrib= urpmi-root= distrib= buildrequires
                      searchmedia= sortmedia= update synthesis= auto-update
                      no-md5sum force-key no-uninstall no-install keep
                      split-level= split-length= clean quiet debug
                      debug-librpm allow-suggests justdb replacepkgs
                      allow-nodeps allow-force parallel= download-all=
                      downloader= curl-options= rsync-options=
                      wget-options= limit-rate= resume retry= proxy-user=
                      verify-rpm no-verify-rpm excludepath= ignorearch
                      ignoresize repackage noscripts nolock P y q
urpmi-valid-options-doc = it uses the getopt syntax
genhdlist-command = /usr/bin/genhdlist2 --allow-empty-media
interactive-allowed-urpmi-commands = /bin/rpm /usr/sbin/urpmi
   /usr/sbin/urpme /usr/sbin/urpmi.addmedia /usr/sbin/urpmi.update
   /usr/sbin/urpmi.removemedia
urpmi-fatal-output = (No space left on device|A requested package cannot be installed)

rpm-command = /bin/rpm
rpm-install-source-command = %(rpm-command)s --nodeps -i
rpm-build-source-command = /usr/bin/rpmbuild
rpm-collect-glob = RPMS/*/*.rpm SRPMS/*.src.rpm
rpm-get-arch-command = %(rpm-command)s --eval '%%{mandriva_arch}'
rpm-get-packager-command = %(rpm-command)s
          --eval '%%{?packager}%%{?!packager:PACKAGER_UNDEFINED}'
rpm-packager-doc = If rpm-packager is not set, then jurt tried to get from
                   rpm-get-packager-command, if it fails, it falls back to
                   rpm-packager-default
rpm-packager = undefined
rpm-packager-default = Jurt Build Bot <root@mandriva.org>
rpm-topdir = ~
rpm-topdir-doc = do not try ~username because it will not work, jurt will
          only try to create this directory if it doesn't exist and set
          proper permissions
rpm-topdir-subdirs = BUILD BUILDROOT RPMS SOURCES SPECS SRPMS
rpm-macros-file = ~/.rpmmacros

root-copy-files = /etc/hosts /etc/resolv.conf
root-post-command = passwd -l root; touch /jurt-root

interactive-packages = sudo
allow-interactive-shell = yes
interactive = no

btrfs-command = /sbin/btrfs
btrfs-create-subvol-command = %(btrfs-command)s subvolume create
btrfs-snapshot-subvol-command = %(btrfs-command)s subvolume snapshot
btrfs-delete-subvol-command = %(btrfs-command)s subvolume delete

#
# used by jurt-root-command and jurt-setup
#
[root]

adduser-command = /usr/sbin/adduser
chroot-command = /usr/bin/env -i /usr/sbin/chroot
su-command = /bin/su -l
su-for-post-command = %(su-command)s -c
sudo-interactive-shell-command = sudo -i
install-command = install
interactive-shell-term = xterm
interactive-shell-command = /usr/bin/env "PS1=\u@$target \w> "
  "TERM=%(interactive-shell-term)s" /bin/bash
sudo-pm-allow-format = $user ALL=(ALL) NOPASSWD: $commands
sudoers = /etc/sudoers
jurt-group = jurt
"""
