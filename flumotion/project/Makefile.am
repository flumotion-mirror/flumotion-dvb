include $(top_srcdir)/common/python.mk
include $(top_srcdir)/common/locale.mk

flumotiondir = $(libdir)/flumotion/python/flumotion/project

flumotion_PYTHON = template.py
flumotion_DATA = template.locale.xml

clean-local:
	rm -f *.pyc *.pyo

PROJECT = template

BUILT_SOURCES = template.py template.locale.xml
CLEANFILES = $(BUILT_SOURCES)

EXTRA_DIST = template.py.in
