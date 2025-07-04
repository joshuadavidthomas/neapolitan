import os
import uuid

from django.core.management import call_command
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils.html import escape

from neapolitan.views import CRUDView, Role, classonlymethod

from .models import Bookmark, NamedCollection, BookmarkTag


class BookmarkView(CRUDView):
    model = Bookmark
    fields = ["url", "title", "note"]
    filterset_fields = [
        "favourite",
    ]


class NamedCollectionView(CRUDView):
    model = NamedCollection
    fields = ["name", "code"]

    lookup_field = "code"
    path_converter = "uuid"

    url_base = "named_collections"


class BookmarkListOnlyView(CRUDView):
    model = Bookmark
    fields = ["url", "title", "note"]
    url_base = "bookmarklist"

    @classonlymethod
    def get_urls(cls, roles=None):
        return super().get_urls(roles={Role.LIST})


class BookmarkTagView(CRUDView):
    model = BookmarkTag
    fields = ["bookmark", "tag"]


urlpatterns = [
    *BookmarkView.get_urls(),
    *NamedCollectionView.get_urls(),
    *BookmarkListOnlyView.get_urls(),
    *BookmarkTagView.get_urls(),
]


class BasicTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.homepage = Bookmark.objects.create(
            url="https://noumenal.es/",
            title="Noumenal • Dr Carlton Gibson",
            note="Carlton Gibson's homepage. Blog, Contact and Project links.",
            favourite=True,
        )
        cls.github = Bookmark.objects.create(
            url="https://github.com/carltongibson",
            title="Carlton Gibson - GitHub",
            note="Carlton Gibson on GitHub",
        )
        cls.fosstodon = Bookmark.objects.create(
            url="https://fosstodon.org/@carlton",
            title="Carlton Gibson - Fosstodon",
            note="Carlton Gibson on Fosstodon",
        )

        cls.main_collection = NamedCollection.objects.create(name="main")

    def test_list(self):
        response = self.client.get("/bookmark/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("filterset", response.context)
        self.assertContains(response, self.homepage.title)
        self.assertContains(response, self.github.title)
        self.assertContains(response, self.fosstodon.title)
        self.assertContains(response, ">Add a new bookmark</a>")

    def test_list_empty(self):
        Bookmark.objects.all().delete()
        response = self.client.get("/bookmark/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "There are no bookmarks. Create one now?")
        self.assertContains(response, ">Add a new bookmark</a>")

    def test_detail(self):
        response = self.client.get(f"/bookmark/{self.homepage.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.homepage.title)
        self.assertContains(response, escape(self.homepage.note))

    def test_create(self):
        create_url = reverse("bookmark-create")

        # Load the form.
        response = self.client.get(create_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'action="/bookmark/new/"')

        # Submit the form.
        response = self.client.post(
            create_url,
            {
                "url": "https://example.com/",
                "title": "Example",
                "note": "Example note",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.resolver_match.url_name, "bookmark-detail")

    def test_delete(self):
        delete_url = reverse("bookmark-delete", args=[self.homepage.pk])

        # Load the form.
        response = self.client.get(delete_url)
        self.assertEqual(response.status_code, 200)

        # Submit the form.
        response = self.client.post(delete_url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.resolver_match.url_name, "bookmark-list")

    def test_update(self):
        update_url = reverse("bookmark-update", args=[self.homepage.pk])

        # Load the form.
        response = self.client.get(update_url)
        self.assertEqual(response.status_code, 200)

        # Submit the form.
        response = self.client.post(
            update_url,
            {
                "url": "https://example.com/",
                "title": "Example",
                "note": "Example note",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertRedirects(
            response, reverse("bookmark-detail", args=[self.homepage.pk])
        )
        self.assertContains(response, "Example")

    def test_filter(self):
        response = self.client.get("/bookmark/?favourite=true")
        self.assertEqual(response.status_code, 200)
        self.assertSequenceEqual([self.homepage], response.context["bookmark_list"])
        self.assertContains(response, self.homepage.title)
        self.assertNotContains(response, self.github.title)
        self.assertNotContains(response, self.fosstodon.title)

    def test_custom_mount_url(self):
        """Test view URL base"""
        response = self.client.get("/collection/")
        self.assertEqual(response.status_code, 404)

        response = self.client.get("/named_collections/")
        self.assertEqual(response.status_code, 200)

    def test_custom_lookup_field(self):
        """Test custom view.lookup_field"""
        response = self.client.get(f"/named_collections/{self.main_collection.code}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.main_collection.name)

    def test_custom_lookup_field_create(self):
        create_url = reverse("named_collections-create")

        # Submit the form.
        response = self.client.post(
            create_url,
            {
                "code": uuid.uuid4(),
                "name": "The Carlton Collection",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.resolver_match.url_name, "named_collections-detail")

    def test_lookup_url_converter(self):
        """Test view.lookup_url_converter"""
        response = self.client.get(f"/named_collections/{self.main_collection.id}/")
        self.assertEqual(response.status_code, 404)

        response = self.client.get(f"/named_collections/{self.main_collection.code}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.main_collection.name)

    def test_overriding_role_initkwargs(self):
        """as_view must prioritise initkwargs over Role extra_initkwargs."""

        class InitKwargsCRUDView(CRUDView):
            model = Bookmark

            def detail(self, request, *args, **kwargs):
                return HttpResponse(self.template_name_suffix)

        view = InitKwargsCRUDView.as_view(
            role=Role.DETAIL, template_name_suffix="_test_suffix"
        )
        request = RequestFactory().get("/")
        response = view(request)
        self.assertContains(response, "_test_suffix")


class RoleTests(TestCase):
    def test_overriding_url_base(self):
        class AlternateCRUDView(CRUDView):
            model = Bookmark
            url_base = "something-else"

        self.assertEqual(AlternateCRUDView.url_base, "something-else")
        self.assertEqual(
            Role.LIST.url_pattern(
                AlternateCRUDView,
            ),
            "something-else/",
        )

    def test_roles_provide_a_url_name_component(self):
        # The URL name is constructed in part by the role value.
        tests = [
            (Role.LIST, "list"),
            (Role.DETAIL, "detail"),
            (Role.CREATE, "create"),
            (Role.UPDATE, "update"),
            (Role.DELETE, "delete"),
        ]
        for role, name in tests:
            with self.subTest(role=role):
                self.assertEqual(role.url_name_component, name)

    def test_url_pattern_generation(self):
        tests = [
            (Role.LIST, "bookmark/"),
            (Role.DETAIL, "bookmark/<int:pk>/"),
            (Role.CREATE, "bookmark/new/"),
            (Role.UPDATE, "bookmark/<int:pk>/edit/"),
            (Role.DELETE, "bookmark/<int:pk>/delete/"),
        ]
        for role, pattern in tests:
            with self.subTest(role=role):
                self.assertEqual(
                    role.url_pattern(BookmarkView),
                    pattern,
                )

    def test_role_url_reversing(self):
        bookmark = Bookmark.objects.create(
            url="https://noumenal.es/",
            title="Noumenal • Dr Carlton Gibson",
            note="Carlton Gibson's homepage. Blog, Contact and Project links.",
            favourite=True,
        )
        tests = [
            (Role.LIST, "/bookmark/"),
            (Role.DETAIL, f"/bookmark/{bookmark.pk}/"),
            (Role.CREATE, "/bookmark/new/"),
            (Role.UPDATE, f"/bookmark/{bookmark.pk}/edit/"),
            (Role.DELETE, f"/bookmark/{bookmark.pk}/delete/"),
        ]
        for role, url in tests:
            with self.subTest(role=role):
                self.assertEqual(
                    role.reverse(BookmarkView, bookmark),
                    url,
                )

    def test_routing_subset_of_roles(self):
        urlpatterns = BookmarkView.get_urls(roles={Role.LIST, Role.DETAIL})
        self.assertEqual(len(urlpatterns), 2)

    def test_rendering_list_only_role(self):
        bookmark = Bookmark.objects.create(
            url="https://noumenal.es/",
            title="Noumenal • Dr Carlton Gibson",
            note="Carlton Gibson's homepage. Blog, Contact and Project links.",
            favourite=True,
        )
        response = self.client.get("/bookmarklist/")
        self.assertEqual(response.status_code, 200)

        for lookup in ["View", "Edit", "Delete"]:
            self.assertNotContains(response, f">{lookup}</a>")

    def test_url_ordering_for_slug_path_converters(self):
        # Ensures correct ordering of URL patterns when using str-based path converters
        # https://github.com/carltongibson/neapolitan/issues/64
        class BookmarkCRUDView(CRUDView):
            model = Bookmark
            path_converter = "slug"
            lookup_url_kwarg = "title"

        # Get the generated URLs
        urls = BookmarkCRUDView.get_urls()

        # Extract paths for the URLs to check ordering
        url_paths = [url.pattern._route for url in urls]

        # Expected order of URL paths
        expected_paths = [
            "bookmark/",  # LIST
            "bookmark/new/",  # CREATE should come before any slug-based URLs
            "bookmark/<slug:title>/",  # DETAIL
            "bookmark/<slug:title>/edit/",  # UPDATE
            "bookmark/<slug:title>/delete/",  # DELETE
        ]

        # Assert that the generated URL paths match the expected order
        self.assertEqual(url_paths, expected_paths)

    def test_role_equality(self):
        """
        Role instances should be equal to themselves but not to other Role
        instances.

        Follows directly from Enum base class, but is preparatory to custom
        roles.
        """
        # Basic examples:
        self.assertEqual(Role.LIST, Role.LIST)
        self.assertNotEqual(Role.LIST, Role.DETAIL)

        # Exhaustive check:
        for role in Role:
            self.assertEqual(role, role)
            for other_role in (r for r in Role if r != role):
                self.assertNotEqual(role, other_role)


class MktemplateCommandTest(TestCase):
    def test_mktemplate_command(self):
        # Run the command
        call_command("mktemplate", "tests.Bookmark", "--list")

        # Check if the file was created
        file_path = "tests/templates/tests/bookmark_list.html"
        self.assertTrue(os.path.isfile(file_path))

        # Remove the created file
        os.remove(file_path)


class ForeignKeyDisplayTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bookmark = Bookmark.objects.create(
            url="https://example.com/",
            title="Example Site",
            note="An example bookmark",
        )
        cls.tag1 = BookmarkTag.objects.create(bookmark=cls.bookmark, tag="python")
        cls.tag2 = BookmarkTag.objects.create(bookmark=cls.bookmark, tag="web")

    def test_foreign_key_display_in_list_view(self):
        response = self.client.get("/bookmarktag/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.bookmark.title)
        self.assertContains(response, "python")
        self.assertContains(response, "web")

    def test_foreign_key_display_in_detail_view(self):
        response = self.client.get(f"/bookmarktag/{self.tag1.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.bookmark.title)
        self.assertContains(response, "python")
