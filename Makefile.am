AUTOMAKE_OPTIONS = dist-bzip2 no-dist-gzip 1.8

ACLOCAL_AMFLAGS = -I m4 -I common

include $(srcdir)/common/changelog.mk
include $(srcdir)/common/common.mk
include $(srcdir)/common/deb.mk
include $(srcdir)/common/pychecker.mk

SUBDIRS = flumotion common misc po

all-local: locale-uninstalled
clean-local: locale-uninstalled-clean

dist: changelog

EXTRA_DIST = \
	env.in \
        .version \
        RELEASE \
	LICENSE.LGPL \
	flumotion-dvb.spec

PYCHECKER_WHITELIST = flumotion/component/dvb/*.py
PYCHECKER_BLACKLIST =

COVERAGE_MODULES = flumotion.component.dvb

BUILT_SOURCES = $(top_srcdir)/.version
$(top_srcdir)/.version:
	echo $(VERSION) > $@-t && mv $@-t $@

.PHONY: ChangeLog
