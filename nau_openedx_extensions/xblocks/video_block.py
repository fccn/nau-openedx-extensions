"""
Custom video block extensions for NAU Open edX.
"""
import re


def get_educast_poster_factory(prev_poster_func):
    """
    Factory to create a customized _poster method for VideoBlock.
    This allows us to inject custom logic while retaining access to the original method.
    """

    def get_educast_poster(self):
        """
        Override the default poster URL logic to customize the poster image.
        """
        poster_url = prev_poster_func(self)
        if not poster_url and self.html5_sources:
            video_src = next(iter(self.html5_sources), None)
            is_educast = 'educast.fccn.pt' in video_src  # to work for both educast staging and production
            if is_educast:
                # from video src like https://staging.educast.fccn.pt/vod/clips/bum66sthd/streaming.m3u8
                # extract the server base url https://educast.fccn.pt or http://educast.fccn.pt or //educast.fccn.pt
                server_base_url = re.match(r'^(https?://[^/]+|//[^/]+)', video_src).group(1)
                # extract the educast video id like bumu66sthd
                educast_video_id = re.search(r'/clips/([^/]+)/', video_src).group(1)
                # construct poster url like https://educast.fccn.pt/img/clips/jpojtray/delivery/cover
                poster_url = f"{server_base_url}/img/clips/{educast_video_id}/delivery/cover"
        return poster_url

    return get_educast_poster
