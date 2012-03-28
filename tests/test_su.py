import tests
import subprocess
from os.path import join

from jurtlib.config import JurtConfig
from jurtlib.su import JurtRootWrapper, AgentError

class TestJurtRootWrapper(tests.Test):

    def setUp(self):
        super(TestJurtRootWrapper, self).setUp()
        self.result = join(self.spooldir, "jurt-wrapper-result")
        self.fake = (join(self.rootdir, "fake_su_wrapper.py")
                + " --result " + self.result)

    def _expect(self, cmd):
        with open(self.result) as f:
            data = f.read()
            lastline = data.strip().splitlines()[-1]
        self.assertTrue(cmd in lastline, "it should have: %r, but had %r" %
                (cmd, lastline))

    def _get_wrapper(self):
        config, sections = self.sample_config()
        suconf = sections[0][1]
        suconf.sudo_command = self.fake
        su = JurtRootWrapper("first", suconf, config)
        return su

    def test_create_wrapper(self):
        su = self._get_wrapper()

    def test_generated_commands(self):
        su = self._get_wrapper()
        su.test_sudo()
        self._expect("/jurt-root-command --type test --target first")
        su.add_user("foolano", 1001)
        self._expect("--type adduser --target first -u 1001 foolano")
        su.run_package_manager("mypm", ["--auto", "foo bar baz", "--mimimi"])
        self._expect("--type runpm --target first --pm mypm -- --auto "
                "\"foo bar baz\" --mimimi")
        su.run_as(["my command", "with", "--some", "args"], "someuser",
                root="/var/roots/some-path")
        self._expect("--type runcmd --target first --root "
                "/var/roots/some-path --run-as someuser -- \"my command\" "
                "with --some args")
        su.rename("from one path", "to another path")
        self._expect("--type rename --target first \"from one path\" "
                "\"to another path\"")
        path = join(self.spooldir, "anydirectory")
        su.mkdir(path, 999, 111)
        self._expect("--type mkdir --target first -u 999 -g 111 "
                "-m 0755 %s" % (path))
        su.mkdir(path, 333, 444, mode="0777")
        self._expect("--type mkdir --target first -u 333 -g 444 "
                "-m 0777 %s" % (path))
        path2 = join(self.spooldir, "another path")
        su.mkdir([path, path2], 333, 444, mode="0777")
        self._expect("--type mkdir --target first -u 333 -g 444 "
                "-m 0777 %s" % (subprocess.list2cmdline([path, path2])))
        su.create_devs("/foo/bar/baz")
        self._expect("--type createdevs --target first --root /foo/bar/baz")
        su.copy("/foo/bar/baz/single path", "/blux/target location")
        self._expect("--type copy --target first "
                "-m 0644 "
                "\"/foo/bar/baz/single path\" "
                "\"/blux/target location\"")
        paths = ["/foo/bar/baz/single path", "/lurg/garg/glux"]
        su.copy(paths, "/blux/target location",
                mode="0755", uid="555", gid="333")
        self._expect("--type copy --target first "
                "-u 555 -g 333 -m 0755 "
                "\"/foo/bar/baz/single path\" "
                "/lurg/garg/glux "
                "\"/blux/target location\"")
        su.copyout(paths, "/blux/target location",
                mode="0755", uid="555", gid="333")
        self._expect("--type copyout --target first "
                "-u 555 -g 333 -m 0755 "
                "\"/foo/bar/baz/single path\" "
                "/lurg/garg/glux "
                "\"/blux/target location\"")
        su.cheapcopy("/foo/bar/some path", "/blux/target location")
        self._expect("--type cheapcopy --target first "
                "\"/foo/bar/some path\" "
                "\"/blux/target location\"")
        su.mount_virtual_filesystems("/my/root/path")
        self._expect("--type mountall --target first --root /my/root/path")
        su.mount_virtual_filesystems("/my/root/path", "myfooarch")
        self._expect("--type mountall --target first --root /my/root/path "
                "--arch myfooarch")
        su.umount_virtual_filesystems("/my/root/path")
        self._expect("--type umountall --target first --root /my/root/path")
        su.umount_virtual_filesystems("/my/root/path", "myfooarch")
        self._expect("--type umountall --target first --root /my/root/path "
                "--arch myfooarch")
        su.compress_root("/my/root/path", "mytargetfile.tar.gz")
        self._expect("--type rootcompress --target first "
                "/my/root/path mytargetfile.tar.gz")
        su.decompress_root("/my/root/path", "mytargetfile.tar.gz")
        self._expect("--type rootdecompress --target first "
                "mytargetfile.tar.gz /my/root/path")
        su.mount_tmpfs("/my/root/path")
        self._expect("--type mounttmpfs --target first "
                "/my/root/path")
        su.umount_tmpfs("/my/root/path")
        self._expect("--type umounttmpfs --target first "
                "/my/root/path")
        su.post_root_command("/my/root/path")
        self._expect("--type postcommand --target first "
                "--root /my/root/path")
        su.post_root_command("/my/root/path", "myfooarch")
        self._expect("--type postcommand --target first "
                "--root /my/root/path --arch myfooarch")
        su.interactive_prepare_conf("myusername", root="/my/root/path")
        self._expect("--type interactiveprepare --target first "
                "--root /my/root/path myusername")
        su.interactive_prepare_conf("myusername", root="/my/root/path",
                arch="myfooarch")
        self._expect("--type interactiveprepare --target first "
                "--root /my/root/path --arch myfooarch myusername")
        su.interactive_shell("myusername", root="/my/root/path")
        self._expect("--type interactiveshell --target first --root "
                "/my/root/path --remount myusername")
        su.btrfs_snapshot("/foo/bar/baz", "/foo/bar/new-baz")
        self._expect("--type btrfssnapshot --target first "
                "/foo/bar/baz /foo/bar/new-baz")

    def test_test_agent_failed(self):
        config, sections = self.sample_config()
        suconf = sections[0][1]
        suconf.sudo_command = "false"
        su = JurtRootWrapper("first", suconf, config)
        self.assertRaises(AgentError, su.test_sudo)
