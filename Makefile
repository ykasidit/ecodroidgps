##### used to run all python unittest files (test_*.py) by command 'make' - running it again will not re-do already passed tests - use 'make clean' to clear the passed state and be able to run all again
MKDIR := $(shell mkdir -p tmp)
SOURCES :=  $(shell find ./ -maxdepth 1 -type f -name 'test_*.py')
OBJS := $(shell find -maxdepth 1 -type f -name 'test_*.py' -printf "tmp/%P_test_output\n" | sort)


run_all_py_unittests: ${OBJS}
	@echo "SUCCESS - ALL TESTS PASSED"

tmp/%.py_test_output: %.py
	@echo "TESTING: $^"
	@python3 $^ > $@ 2>&1 || (mv -f $@ $@_failed ; echo "FAILED - SEE DETAILS IN FILE: $@_failed --- dumping it below: " ; cat "$@_failed" ; exit 1)

clean:
	rm -f $(OBJS)
