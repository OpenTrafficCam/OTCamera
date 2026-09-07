from pathlib import Path

from OTCamera.plugin.upload.s3_upload import S3Upload


class TestDescribe:
    def test_answers_without_touching_the_client(self) -> None:
        upload = S3Upload(s3client=None, bucket_name="videos", key_prefix="site/cam")

        result = upload.describe(Path("/videos/uploaded/cam_2026-08-12_10-00-00.h264"))

        assert result.bucket == "videos"
        assert result.key == "site/cam/cam_2026-08-12_10-00-00.h264"

    def test_the_filename_is_the_key_without_a_prefix(self) -> None:
        upload = S3Upload(s3client=None, bucket_name="videos")

        result = upload.describe(Path("/videos/clip.h264"))

        assert result.key == "clip.h264"

    def test_the_answer_does_not_depend_on_where_the_file_lies(self) -> None:
        upload = S3Upload(s3client=None, bucket_name="videos", key_prefix="site/cam")

        pending = upload.describe(Path("/videos/pending/clip.h264"))
        uploaded = upload.describe(Path("/videos/uploaded/clip.h264"))

        assert pending.key == uploaded.key
