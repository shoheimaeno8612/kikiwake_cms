import argparse

from .config import load_settings
from .services import (
    audio_alignment,
    audio_duration_backfill,
    audio_feature_extraction,
    audio_generation,
    content_generation,
    feature_extraction,
    json_export,
    translation,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kikiwake-cms",
        description="Data generation pipeline for the personalized dictation app",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_content = subparsers.add_parser(
        "generate-content", help="Generate contents and their audio in batch."
    )
    generate_content.add_argument(
        "-c", "--count", required=True, type=int, help="Number of contents to generate."
    )
    generate_content.add_argument(
        "-m", "--model", required=True, help="Model used to generate contents."
    )

    subparsers.add_parser(
        "generate-audio", help="Generate audio for contents that have no audio yet."
    )

    subparsers.add_parser(
        "backfill-audio-duration",
        help="Recompute duration for audio records where duration is 0.",
    )

    subparsers.add_parser(
        "analyze-audio-alignment",
        help="Determine per-sentence start/end times using Gemini.",
    )

    subparsers.add_parser(
        "translate-sentences", help="Translate sentences that have no translation yet."
    )

    extract_features = subparsers.add_parser(
        "extract-features", help="Extract linguistic features from sentences."
    )
    extract_features.add_argument(
        "-c",
        "--count",
        required=True,
        type=int,
        help="Number of contents executed for the feature extraction.",
    )
    extract_features.add_argument(
        "-m", "--model", required=True, help="Model used for the feature extraction."
    )

    extract_audio_features = subparsers.add_parser(
        "extract-audio-features",
        help="Extract audio features (connected speech) and utterance segments from audio.",
    )
    extract_audio_features.add_argument(
        "-c",
        "--count",
        required=True,
        type=int,
        help="Number of audio processed for the audio feature extraction.",
    )
    extract_audio_features.add_argument(
        "-m",
        "--model",
        required=True,
        help="Model used for the audio feature extraction.",
    )

    subparsers.add_parser(
        "export-json", help="Export contents as JSON files to R2, grouped by level/target/category."
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    settings = load_settings()

    if args.command == "generate-content":
        content_generation.run(count=args.count, gen_model=args.model, settings=settings)
    elif args.command == "generate-audio":
        audio_generation.run(settings=settings)
    elif args.command == "backfill-audio-duration":
        audio_duration_backfill.run(settings=settings)
    elif args.command == "analyze-audio-alignment":
        audio_alignment.run(settings=settings)
    elif args.command == "translate-sentences":
        translation.run(settings=settings)
    elif args.command == "extract-features":
        feature_extraction.run(count=args.count, gen_model=args.model, settings=settings)
    elif args.command == "extract-audio-features":
        audio_feature_extraction.run(
            count=args.count, gen_model=args.model, settings=settings
        )
    elif args.command == "export-json":
        json_export.run(settings=settings)


if __name__ == "__main__":
    main()
