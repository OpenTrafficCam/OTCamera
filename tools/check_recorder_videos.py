from pathlib import Path

import pandas as pd


def collect_video_data(video_check_path: str, results_name: str = "video_check.csv"):
    video_check_path = Path(video_check_path).expanduser().resolve()
    result_csv = video_check_path.absolute() / results_name

    h264_videos = video_check_path.glob(("**/*.h264"))

    with open(result_csv, "w") as f:
        f.write("camera,framerate,datetime,filesize")
        f.write("\n")

        for video in h264_videos:
            (cam, fr, date, time) = video.stem.split("_")
            size = video.stat().st_size / 1024 / 1024
            dir = video.parent.stem
            if not dir.startswith("."):
                f.write(f"{cam},{fr},{date}_{time},{size:.2f}")
                f.write("\n")


def format_video_check(video_check_path: str, results_name: str):
    video_check_path = Path(video_check_path).expanduser().resolve()
    result_csv = video_check_path.absolute() / results_name

    results = pd.read_csv(result_csv, sep=",")
    results = results.pivot(index="datetime", columns="camera", values="filesize")
    results.to_csv(result_csv.with_stem(result_csv.stem + "_formatted"))
    results.to_excel(
        result_csv.with_stem(result_csv.stem + "_formatted").with_suffix(".xlsx")
    )


if __name__ == "__main__":
    video_check_path = (
        r"/Volumes/platomo data/Projekte/002 BASt Tempo30/2022-10-16_Saarbrücken/"
    )
    results_name = "video_check.csv"
    collect_video_data(video_check_path, results_name)
    format_video_check(video_check_path, results_name)
