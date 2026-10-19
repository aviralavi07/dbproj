"""Website checks: every page and link opens, policy pages and favicon exist,
and the pages follow the design rules of the project."""
import os
import re
import unittest
from html.parser import HTMLParser

from tests.test_app import Base, ROOT

SEEDS = ["/", "/design", "/testing", "/team", "/privacy", "/terms", "/dashboard", "/clients", "/tiers",
         "/subscriptions", "/invoices", "/tickets", "/usage", "/reports"]
DASHES = re.compile("[\u2012\u2013\u2014\u2015]")
EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D]")


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls, self.imgs, self.h1 = [], [], 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for key in ("href", "src"):
            if a.get(key):
                self.urls.append(a[key])
        if tag == "img":
            self.imgs.append(a)
        if tag == "h1":
            self.h1 += 1


class SiteChecks(Base):
    def crawl(self):
        """Open every page reachable by links from the seed pages. Returns {url: html}."""
        seen, pages, queue = set(), {}, list(SEEDS)
        while queue:
            url = queue.pop(0).split("#")[0]
            if url in seen:
                continue
            seen.add(url)
            r = self.c.get(url, follow_redirects=True)
            self.assertEqual(r.status_code, 200, "page does not open: " + url)
            if "text/html" in r.content_type:
                html = r.get_data(as_text=True)
                pages[url] = html
                p = Links()
                p.feed(html)
                queue += [u for u in p.urls if u.startswith("/")]
        return pages

    def test_SC01_home_page_opens(self):
        """Home page opens and has links to the application and the database design"""
        code, html = self.get("/")
        self.assertEqual(code, 200)
        self.assertIn("Cloud SaaS Subscription and Billing Management System", html)
        self.assertIn('href="/dashboard"', html)
        self.assertIn('href="/design"', html)

    def test_SC02_every_link_and_file_opens(self):
        """Every internal link, image, style sheet and icon on every page opens"""
        pages = self.crawl()
        self.assertGreater(len(pages), 40)

    def test_SC03_privacy_policy_page(self):
        """Privacy Policy page exists and explains cookies and data storage"""
        code, html = self.get("/privacy")
        self.assertEqual(code, 200)
        self.assertIn("Privacy Policy", html)
        self.assertIn("cookie", html)
        self.assertIn("MySQL database", html)

    def test_SC04_terms_page(self):
        """Terms and Conditions page exists"""
        code, html = self.get("/terms")
        self.assertEqual(code, 200)
        self.assertIn("Terms and Conditions", html)
        self.assertIn("No payments are processed", html)

    def test_SC05_footer_links_on_every_page(self):
        """Every page links to the Privacy Policy and the Terms and Conditions"""
        for url, html in self.crawl().items():
            self.assertIn('href="/privacy"', html, url)
            self.assertIn('href="/terms"', html, url)

    def test_SC06_favicon_is_available(self):
        """Favicon is served and every page points to it"""
        r = self.c.get("/favicon.ico")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content_type.startswith("image/"))
        for url, html in self.crawl().items():
            self.assertIn("favicon.ico", html, url)

    def test_SC07_no_em_or_en_dashes(self):
        """No em dash or en dash appears on any page"""
        for url, html in self.crawl().items():
            self.assertIsNone(DASHES.search(html), url)

    def test_SC08_no_emoji(self):
        """No emoji or pictograph appears on any page"""
        for url, html in self.crawl().items():
            self.assertIsNone(EMOJI.search(html), url)

    def test_SC09_no_external_resources(self):
        """No page loads or links to anything outside the local site"""
        for url, html in self.crawl().items():
            p = Links()
            p.feed(html)
            external = [u for u in p.urls if re.match(r"(https?:)?//", u)]
            self.assertEqual(external, [], url)

    def test_SC10_no_scripts_or_animation(self):
        """No JavaScript, so no scroll animation, cursor effect or animated counter"""
        for url, html in self.crawl().items():
            self.assertNotIn("<script", html.lower(), url)
        css = open(os.path.join(ROOT, "static", "style.css"), encoding="utf-8").read().lower()
        for word in ("animation", "@keyframes", "transition", "transform", "cursor:url"):
            self.assertNotIn(word, css)

    def test_SC11_flat_style_without_gradients_or_pills(self):
        """Style sheet has no gradients and no rounded pill shapes (radius 4px at most)"""
        css = open(os.path.join(ROOT, "static", "style.css"), encoding="utf-8").read().lower()
        self.assertNotIn("gradient", css)
        self.assertNotIn("box-shadow", css)
        radii = [int(x) for x in re.findall(r"border-radius:\s*(\d+)px", css)]
        self.assertTrue(radii)
        self.assertLessEqual(max(radii), 4)
        self.assertNotIn("%", "".join(re.findall(r"border-radius:[^;]*", css)))

    def test_SC12_no_ai_tag_or_generator_text(self):
        """No made-with, generated-by or AI tag appears on any page"""
        bad = re.compile(r"made with|generated by|built with|powered by|ai-generated|<meta[^>]+generator", re.I)
        for url, html in self.crawl().items():
            self.assertIsNone(bad.search(html), url)

    def test_SC13_images_have_alt_text(self):
        """Every image has alternative text"""
        for url, html in self.crawl().items():
            p = Links()
            p.feed(html)
            for img in p.imgs:
                self.assertTrue((img.get("alt") or "").strip(), url)

    def test_SC14_each_page_has_one_heading_and_a_title(self):
        """Every page has exactly one main heading and a page title"""
        for url, html in self.crawl().items():
            p = Links()
            p.feed(html)
            self.assertEqual(p.h1, 1, url)
            self.assertRegex(html, r"<title>[^<]+ \| Cloud SaaS Billing</title>")
            if url != "/":
                self.assertNotIn("<title>Home |", html, url)       # only the home page is called Home

    def test_SC15_unknown_page_shows_site_navigation(self):
        """An unknown address shows the not-found page inside the site layout"""
        code, html = self.get("/no-such-page")
        self.assertEqual(code, 404)
        self.assertIn("Privacy Policy", html)
        self.assertIn('href="/design"', html)

    def test_SC16_site_only_listens_on_localhost(self):
        """The server is started for this computer only (127.0.0.1)"""
        src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
        self.assertIn('host="127.0.0.1"', src)
        self.assertIn("debug=False", src)

    def test_SC17_stated_test_count_matches_the_tests(self):
        """The test count written on the site matches the real number of test cases"""
        _, home = self.get("/")
        _, testing = self.get("/testing")
        rows = re.findall(r"<td>TC\d+</td>", testing)
        self.assertEqual(len(rows), 57)
        self.assertIn("57 test cases", home)

    def test_SC18_application_menu_only_inside_the_application(self):
        """Overview pages show the site menu only; application pages add the module menu"""
        _, home = self.get("/")
        _, clients = self.get("/clients")
        self.assertNotIn('aria-label="Application"', home)
        self.assertIn('aria-label="Application"', clients)


if __name__ == "__main__":
    unittest.main(verbosity=2)
