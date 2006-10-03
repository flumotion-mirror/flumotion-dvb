include $(top_srcdir)/common/python.mk
include $(top_srcdir)/common/trial.mk

BUILT_SOURCES = setup.py
CLEANFILES = $(BUILT_SOURCES)

EXTRA_DIST = 				\
	__init__.py			\
	common.py			\
	test_sample_admin_gtk.py	\
	test_sample_common.py

check-local: trial
