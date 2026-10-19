"""Run all test cases and print a result table:   python run_tests.py"""
import sys
import unittest

from tests import test_app, test_site


class Result(unittest.TextTestResult):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.table = []

    def _add(self, test, status):
        doc = (test.shortDescription() or "").strip()
        self.table.append((test._testMethodName.split("_")[1], doc, status))

    def addSuccess(self, test):
        super().addSuccess(test); self._add(test, "PASS")

    def addFailure(self, test, err):
        super().addFailure(test, err); self._add(test, "FAIL")

    def addError(self, test, err):
        super().addError(test, err); self._add(test, "ERROR")


if __name__ == "__main__":
    suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromModule(test_app),
                                unittest.defaultTestLoader.loadTestsFromModule(test_site)])
    runner = unittest.TextTestRunner(resultclass=Result, verbosity=0, stream=open("nul" if sys.platform == "win32" else "/dev/null", "w"))
    result = runner.run(suite)
    print("%-6s %-78s %s" % ("ID", "Test case", "Result"))
    print("-" * 94)
    for title, prefix in (("Application test cases", "TC"), ("Website checks", "SC")):
        part = [r for r in sorted(result.table) if r[0].startswith(prefix)]
        for tid, doc, status in part:
            print("%-6s %-78s %s" % (tid, doc[:78], status))
        print("-" * 94)
        passed = sum(1 for r in part if r[2] == "PASS")
        print("%s: %d   Passed: %d   Failed: %d" % (title, len(part), passed, len(part) - passed))
        print()
    for test, tb in result.failures + result.errors:
        print("\n", test, "\n", tb)
    sys.exit(0 if result.wasSuccessful() else 1)
