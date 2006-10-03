include $(top_srcdir)/common/python.mk
include $(top_srcdir)/common/locale.mk

flumotiondir = $(libdir)/flumotion/python/flumotion/project

flumotion_PYTHON = dvb.py
flumotion_DATA = dvb.locale.xml

clean-local:
	rm -f *.pyc *.pyo

PROJECT = dvb

BUILT_SOURCES = dvb.py dvb.locale.xml
CLEANFILES = $(BUILT_SOURCES)

EXTRA_DIST = dvb.py.in
