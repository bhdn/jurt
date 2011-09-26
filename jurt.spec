Name:		jurt
Summary:	A package builder
Version:	0.02
Release:	1
Source0:	%name-%version.tar.gz
URL:		http://gitorious.org/jurt
Group:		Development/Python
BuildRoot:	%_tmppath/%name-%version-%release-buildroot
License:	GPLv2

BuildRequires:	python-devel

Requires:	python
Requires:	sudo

%description
Jurt is a package builder.

%package suid
Summary: a suid wrapper for jurt
Group: Development/Python

%description suid
a suid wrapper for jurt

%prep
%setup -q

%build
%__python setup.py build
%make jurt-suid 

%install
%__rm -rf %buildroot
%__python setup.py install --root=%buildroot
install -d %buildroot/%_sbindir/
mv %buildroot/%_bindir/jurt-{root-command,setup} %buildroot/%_sbindir/
mv jurt-suid %buildroot/%_sbindir/

install -d %buildroot/%_var/spool/jurt/builds/
install -m 1770 -d %buildroot/%_var/spool/jurt/builds/spools/
install -m 1770 -d %buildroot/%_var/spool/jurt/builds/logs/
install -m 1770 -d %buildroot/%_var/spool/jurt/builds/fail/
install -m 1770 -d %buildroot/%_var/spool/jurt/builds/success/
install -m 1770 -d %buildroot/%_var/spool/jurt/chroots/
install -m 1770 -d %buildroot/%_var/spool/jurt/chroots/temp/
install -m 1770 -d %buildroot/%_var/spool/jurt/chroots/active/
install -m 1770 -d %buildroot/%_var/spool/jurt/chroots/old/
install -m 1770 -d %buildroot/%_var/spool/jurt/chroots/keep/
install -m 0770 -d %buildroot/%_var/spool/jurt/chroots/cached

%clean
%__rm -rf %buildroot

%pre
%_pre_useradd jurt /var/empty /sbin/nologin

%postun
%_postun_userdel jurt

%files
%defattr(-,root,root)
%doc README LICENSE
%config(noreplace) %_sysconfdir/jurt/jurt.conf
%{py_sitedir}/*
%_sbindir/jurt-root-command
%_sbindir/jurt-setup
%_bindir/jurt
%_bindir/jurt-build
%_bindir/jurt-shell
%_bindir/jurt-put
%_bindir/jurt-showrc
%_bindir/jurt-list-targets
%_bindir/jurt-list-roots
%_bindir/jurt-test-sudo
%attr(1770,root,jurt) %dir %_var/spool/jurt/builds/spools/
%attr(1770,root,jurt) %dir %_var/spool/jurt/builds/logs/
%attr(1770,root,jurt) %dir %_var/spool/jurt/builds/fail/
%attr(1770,root,jurt) %dir %_var/spool/jurt/builds/success/
%attr(1770,root,jurt) %dir %_var/spool/jurt/chroots/
%attr(1770,root,jurt) %dir %_var/spool/jurt/chroots/temp/
%attr(1770,root,jurt) %dir %_var/spool/jurt/chroots/active/
%attr(1770,root,jurt) %dir %_var/spool/jurt/chroots/old/
%attr(1770,root,jurt) %dir %_var/spool/jurt/chroots/keep/
%_var/spool/jurt/chroots/cached/

%files suid
%_sbindir/jurt-suid
