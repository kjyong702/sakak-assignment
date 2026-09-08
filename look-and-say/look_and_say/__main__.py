import argparse

from look_and_say.naive import middle_two


def main() -> None:
    parser = argparse.ArgumentParser(description="개미수열 n번째 항의 가운데 두 자리")
    parser.add_argument("n", type=int, help="항 번호 (3 < n < 100)")
    args = parser.parse_args()
    print(middle_two(args.n))


if __name__ == "__main__":
    main()
