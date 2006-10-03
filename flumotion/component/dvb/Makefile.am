include $(top_srcdir)/common/python.mk

component_PYTHON = __init__.py sample.py admin_gtk.py common.py
componentdir = $(libdir)/flumotion/python/flumotion/component/sample
component_DATA = \
	sample.xml \
	sample.glade

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
