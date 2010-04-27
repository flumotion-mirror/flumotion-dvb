include $(top_srcdir)/common/python.mk

component_PYTHON = __init__.py dvb.py admin_gtk.py wizard_gtk.py dvbchecks.py
componentdir = $(libdir)/flumotion/python/flumotion/component/dvb
component_DATA = \
	dvb.xml \
	dvb.glade \
	wizard.glade

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
