all: jurt-suid
install:
	install -m 770 jurt-suid $(DESTDIR)/usr/sbin/
