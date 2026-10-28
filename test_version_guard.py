import unittest

from version_guard import extract_symbols, judge, build_query, code_blocks


def symbols(code):
    return {(s["lib"], s["symbol"], s["kind"]) for s in extract_symbols(code)}


def page(url, passage):
    return {"url": url, "title": "t", "passage": passage, "content": ""}


class ExtractTest(unittest.TestCase):
    def test_resolves_aliases_and_from_imports(self):
        found = symbols("import numpy as np\nfrom datetime import datetime\n"
                        "x = np.float_(1)\nt = datetime.utcnow()\n")
        self.assertIn(("numpy", "numpy.float_", "attr"), found)
        self.assertIn(("python", "datetime.datetime.utcnow", "attr"), found)

    def test_removed_module_import_is_a_symbol(self):
        self.assertIn(("python", "imp", "module"), symbols("import imp\nimp.reload(x)\n"))
        self.assertIn(("python", "distutils", "module"), symbols("from distutils.core import setup\n"))

    def test_unknown_receiver_methods_attach_to_third_party_lib(self):
        found = symbols("import pandas as pd\ndf = pd.DataFrame()\ndf = df.append({'a': 1}, ignore_index=True)\n")
        self.assertIn(("pandas", "append", "method"), found)
        self.assertIn(("pandas", "append(ignore_index=)", "keyword"), found)

    def test_keyword_on_unknown_receiver(self):
        found = symbols("import pandas as pd\ndf = pd.read_csv('a')\ndf.fillna(method='ffill')\n")
        self.assertIn(("pandas", "fillna(method=)", "keyword"), found)

    def test_variable_tied_to_creating_library(self):
        found = symbols("import pandas as pd\nimport numpy as np\ndf = pd.read_csv('a')\ndf = df.append({})\n")
        self.assertIn(("pandas", "append", "method"), found)
        self.assertNotIn(("numpy", "append", "method"), found)

    def test_third_party_top_module_not_searched(self):
        found = symbols("import pandas as pd\nimport json\n")
        self.assertNotIn(("pandas", "pandas", "module"), found)
        self.assertIn(("python", "json", "module"), found)

    def test_generic_names_skipped(self):
        found = symbols("import pandas as pd\ndf = pd.DataFrame()\ndf.head()\n")
        self.assertNotIn(("pandas", "head", "method"), found)

    def test_query_length(self):
        sym = extract_symbols("import pandas as pd\npd.read_csv('a', delim_whitespace=True)\n")
        for s in sym:
            self.assertLessEqual(len(build_query(s)), 64)

    def test_code_blocks(self):
        self.assertEqual(code_blocks("text\n```python\nx = 1\n```\n"), ["x = 1\n"])
        self.assertEqual(code_blocks("x = 1"), ["x = 1"])


class JudgeTest(unittest.TestCase):
    SITE = "pandas.pydata.org"

    def test_removed_sentence(self):
        pages = [page("https://pandas.pydata.org/docs/whatsnew/v2.0.0.html",
                      "Removed deprecated Series.append(), DataFrame.append(), use concat() instead (GH 35407)")]
        self.assertEqual(judge(pages, self.SITE, ["append"], ["append"])["verdict"], "breaking")

    def test_replacement_is_not_flagged(self):
        pages = [page("https://pandas.pydata.org/docs/whatsnew/v2.0.0.html",
                      "Removed deprecated Series.append(), DataFrame.append(), use concat() instead (GH 35407)")]
        self.assertEqual(judge(pages, self.SITE, ["concat"], ["concat"])["verdict"], "no_evidence")

    def test_owner_class_is_not_flagged(self):
        pages = [page("https://pandas.pydata.org/docs/whatsnew/v3.0.0.html",
                      "Removed DataFrame.applymap, Styler.applymap and Styler.applymap_index (GH 52364)")]
        self.assertEqual(judge(pages, self.SITE, ["DataFrame"], ["DataFrame"])["verdict"], "no_evidence")
        self.assertEqual(judge(pages, self.SITE, ["applymap"], ["applymap"])["verdict"], "breaking")

    def test_pending_removal_is_deprecated(self):
        pages = [page("https://docs.python.org/3/whatsnew/3.12.html",
                      "datetime.datetime's utcnow() and utcfromtimestamp() are deprecated and will be removed in a future version.")]
        self.assertEqual(judge(pages, "docs.python.org", ["datetime.utcnow"], ["utcnow"])["verdict"], "deprecated")

    def test_non_official_domain_ignored(self):
        pages = [page("https://stackoverflow.com/q/1", "DataFrame.append was removed in pandas 2.0")]
        self.assertEqual(judge(pages, self.SITE, ["append"], ["append"])["verdict"], "no_evidence")

    def test_strict_then_loose(self):
        pages = [page("https://docs.python.org/3/whatsnew/3.12.html",
                      "datetime.datetime's utcnow() and utcfromtimestamp() are deprecated and will be removed.")]
        result = judge(pages, "docs.python.org", ["datetime.utcnow"], ["utcnow"])
        self.assertEqual(result["match"], "loose")

    def test_migration_table_row(self):
        pages = [page("https://numpy.org/doc/2.1/numpy_2_0_migration_guide.html",
                      "trapz Use np.trapezoid or a scipy.integrate function instead.")]
        self.assertEqual(judge(pages, "numpy.org", ["trapz"], ["trapz"])["verdict"], "deprecated")
        self.assertEqual(judge(pages, "numpy.org", ["trapezoid"], ["trapezoid"])["verdict"], "no_evidence")

    def test_code_symbol_must_look_like_code(self):
        pages = [page("https://pandas.pydata.org/docs/x.html",
                      "If the DataFrame has a MultiIndex, this method can remove one or more levels.")]
        self.assertEqual(judge(pages, self.SITE, ["DataFrame"], ["DataFrame"], "attr")["verdict"], "no_evidence")
        pages = [page("https://docs.python.org/3/whatsnew/3.12.html",
                      "Remove the ssl.wrap_socket() function, deprecated in Python 3.7.")]
        self.assertEqual(judge(pages, "docs.python.org", ["wrap_socket"], ["wrap_socket"], "attr")["verdict"], "breaking")

    def test_section_label_not_flagged(self):
        pages = [page("https://docs.python.org/3/whatsnew/3.13.html",
                      "sys: 自 Python 3.13 起,_enablelegacywindowsfsencoding() 函式已被棄用。")]
        self.assertEqual(judge(pages, "docs.python.org", ["sys"], ["sys"], "module")["verdict"], "no_evidence")

    def test_module_needs_module_context(self):
        prose = [page("https://docs.python.org/3/howto/sockets.html",
                      "Most socket libraries are so used to programmers neglecting this that they no longer care.")]
        self.assertEqual(judge(prose, "docs.python.org", ["socket"], ["socket"], "module")["verdict"], "no_evidence")
        removal = [page("https://docs.python.org/3/whatsnew/3.12.html",
                        "The asynchat, asyncore, and imp modules have been removed.")]
        self.assertEqual(judge(removal, "docs.python.org", ["imp"], ["imp"], "module")["verdict"], "breaking")

    def test_normal_error_behaviour_is_not_a_change(self):
        pages = [page("https://requests.readthedocs.io/en/latest/",
                      "Response.raise_for_status() will raise an HTTPError if the request returned an unsuccessful status code.")]
        self.assertEqual(judge(pages, "requests.readthedocs.io", ["raise_for_status"], ["raise_for_status"], "method")["verdict"], "mentioned")

    def test_status_word_must_be_near_symbol(self):
        blob = ("asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop) " + "x " * 100 +
                "builtins: ~True is deprecated and will be removed.")
        pages = [page("https://docs.python.org/3/whatsnew/3.14.html", blob)]
        self.assertEqual(judge(pages, "docs.python.org", ["run"], ["run"], "attr")["verdict"], "mentioned")

    def test_prose_remove_is_not_removal(self):
        pages = [page("https://numpy.org/doc/stable/x.html",
                      "See also np.squeeze; reshape can insert, remove, and combine dimensions of np.array.")]
        self.assertEqual(judge(pages, "numpy.org", ["array"], ["array"], "attr")["verdict"], "mentioned")

    def test_module_function_matched_by_name(self):
        strict = {s["symbol"]: s["strict"] for s in extract_symbols("import numpy as np\nnp.trapz([1], [2])\n")}
        self.assertEqual(strict["numpy.trapz"], ["trapz"])

    def test_possessive_owner_not_flagged(self):
        pages = [page("https://docs.python.org/3/whatsnew/3.12.html",
                      "datetime.datetime's utcnow() and utcfromtimestamp() are deprecated.")]
        self.assertEqual(judge(pages, "docs.python.org", ["datetime"], ["datetime"])["verdict"], "no_evidence")


if __name__ == "__main__":
    unittest.main()
