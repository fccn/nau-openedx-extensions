"""
Test cases for the customized VideoBlock _poster method for Educast videos.
"""
from django.test import TestCase

from nau_openedx_extensions.xblocks.video_block import get_educast_poster_factory


class FakeVideoBlock():
    """
    A fake VideoBlock XBlock class for testing
    """
    def __init__(self):
        self.html5_sources = {}


class TestVideoBlock(TestCase):
    """
    Test cases for the customized VideoBlock _poster method for Educast videos.
    """
    def test_get_educast_poster_https(self):
        """
        Test the customized _poster method for VideoBlock.
        """
        # Create a mock previous _poster method
        def mock_prev_poster(self):  # pylint: disable=unused-argument
            return None

        # Create the customized _poster method
        customized_poster_method = get_educast_poster_factory(mock_prev_poster)

        # Create an instance of VideoBlock and set html5_sources
        video_block = FakeVideoBlock()
        video_block.html5_sources = ['https://dev.educast.fccn.pt/vod/clips/bum66sthd/streaming.m3u8']

        # Call the customized _poster method
        poster_url = customized_poster_method(video_block)

        # Verify the poster URL is as expected
        expected_url = 'https://dev.educast.fccn.pt/img/clips/bum66sthd/delivery/cover'
        self.assertEqual(poster_url, expected_url)

    def test_get_educast_poster_http(self):
        """
        Test the customized _poster method for VideoBlock.
        """
        # Create a mock previous _poster method
        def mock_prev_poster(self):  # pylint: disable=unused-argument
            return None

        # Create the customized _poster method
        customized_poster_method = get_educast_poster_factory(mock_prev_poster)

        # Create an instance of VideoBlock and set html5_sources
        video_block = FakeVideoBlock()
        video_block.html5_sources = ['http://educast.fccn.pt/vod/clips/fdgfdgfdgfdg/streaming.m3u8']

        # Call the customized _poster method
        poster_url = customized_poster_method(video_block)

        # Verify the poster URL is as expected
        expected_url = 'http://educast.fccn.pt/img/clips/fdgfdgfdgfdg/delivery/cover'
        self.assertEqual(poster_url, expected_url)

    def test_get_educast_poster_no_protocol(self):
        """
        Test the customized _poster method for VideoBlock.
        """
        # Create a mock previous _poster method
        def mock_prev_poster(self):  # pylint: disable=unused-argument
            return None

        # Create the customized _poster method
        customized_poster_method = get_educast_poster_factory(mock_prev_poster)

        # Create an instance of VideoBlock and set html5_sources
        video_block = FakeVideoBlock()
        video_block.html5_sources = ['//educast.fccn.pt/vod/clips/aaaaaa/streaming.m3u8']

        # Call the customized _poster method
        poster_url = customized_poster_method(video_block)

        # Verify the poster URL is as expected
        expected_url = '//educast.fccn.pt/img/clips/aaaaaa/delivery/cover'
        self.assertEqual(poster_url, expected_url)
