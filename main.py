import cv2
import os
import sys

# ファイル選択ダイアログ用
import tkinter as tk
from tkinter import filedialog


def has_ffmpeg_support() -> bool:
    """OpenCV が FFMPEG 付きでビルドされているか確認する。"""
    try:
        info = cv2.getBuildInformation()
    except Exception:
        return False

    return "FFMPEG:YES" in info.upper().replace(" ", "")


def create_capture(video_path: str) -> tuple[cv2.VideoCapture, str]:
    """FFMPEG が使えれば CAP_FFMPEG で開き、だめなら既定バックエンドにフォールバック。"""
    if has_ffmpeg_support():
        cap = cv2.VideoCapture(video_path, cv2.CAP_FFMPEG)
        if cap.isOpened():
            return cap, "FFMPEG"
        cap.release()
        print("FFMPEG バックエンドで開けませんでした。標準バックエンドにフォールバックします。")

    cap = cv2.VideoCapture(video_path)
    return cap, "DEFAULT"


def save_frame(filepath: str, frame) -> bool:
    """Windows の日本語 UNC パスで imwrite が失敗する場合に備え、imencode で書き込む。"""
    try:
        ok, buf = cv2.imencode(".png", frame)
    except Exception as e:
        print(f"imencode 失敗: {e}")
        return False

    if not ok:
        return False

    try:
        with open(filepath, "wb") as f:
            f.write(buf.tobytes())
        return True
    except Exception as e:
        print(f"ファイル書き込みに失敗しました: {e}")
        return False


def format_time_msec(msec: float) -> str:
    """
    動画の経過時間（ミリ秒）を mmssmmm 形式の文字列にフォーマットする。
    例：12345 ms -> "0000m12s345ms"
    """
    total_ms = int(round(msec))
    total_seconds = total_ms // 1000
    ms = total_ms % 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:04d}m{seconds:02d}s{ms:03d}ms"


def select_video_file_via_dialog() -> str | None:
    root = tk.Tk()
    root.withdraw()

    filetypes = [
        ("Video files", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.m4v"),
        ("All files", "*.*"),
    ]

    video_path = filedialog.askopenfilename(
        title="動画ファイルを選択してください",
        filetypes=filetypes,
    )

    root.destroy()

    if not video_path:
        return None

    return video_path


def resolve_video_path_from_args_or_dialog() -> str | None:
    if len(sys.argv) >= 2:
        path = sys.argv[1]
        if os.path.exists(path):
            return path
        else:
            print(f"指定された動画ファイルが見つかりません: {path}")
            return None
    else:
        print("コマンドライン引数が指定されていないため、動画ファイル選択ダイアログを開きます。")
        return select_video_file_via_dialog()


def reopen_and_seek_to_frame(video_path: str, target_frame_index: int):
    cap, backend = create_capture(video_path)
    if not cap.isOpened():
        print("動画ファイルを再オープンできませんでした。")
        return None, None

    current_frame = 0
    frame = None
    while current_frame < target_frame_index:
        ret, frame = cap.read()
        if not ret:
            print("指定されたフレーム位置まで到達できませんでした。動画の最後かもしれません。")
            break
        current_frame += 1

    if frame is None:
        cap.release()
        return None, None

    return cap, frame


def main():
    video_path = resolve_video_path_from_args_or_dialog()
    if not video_path:
        print("動画ファイルが選択されなかったため、終了します。")
        sys.exit(1)

    if not os.path.exists(video_path):
        print(f"動画ファイルが見つかりません: {video_path}")
        sys.exit(1)

    base_dir = os.path.dirname(os.path.abspath(video_path))
    output_dir = os.path.join(base_dir, "snapshots")
    os.makedirs(output_dir, exist_ok=True)

    cap, backend = create_capture(video_path)
    if not cap.isOpened():
        print("動画ファイルを開けませんでした。コーデックなどを確認してください。")
        sys.exit(1)
    print(f"使用バックエンド: {backend}")

    window_name = "Video (space: play/pause, s: snapshot, a/d: frame step, r/R: resize, q or ×: quit)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    # 起動直後は一時停止状態にする
    paused = True

    # まず 1 フレームだけ読み込む
    ret, frame = cap.read()
    if not ret:
        print("動画からフレームを読み込めませんでした。")
        cap.release()
        cv2.destroyAllWindows()
        sys.exit(1)

    frame_index = 1  # 1 フレーム目から開始

    # 元のフレームサイズ（リセット用）
    orig_height, orig_width = frame.shape[:2]
    orig_aspect = orig_width / orig_height

    # 起動直後はフレームサイズに合わせる
    cv2.resizeWindow(window_name, orig_width, orig_height)

    print(f"動画ファイル: {video_path}")
    print("操作方法:")
    print("  space : 再生 / 一時停止")
    print("  s     : スナップショットを保存")
    print("  a     : 一時停止中に 1 フレーム戻す")
    print("  d     : 一時停止中に 1 フレーム進める")
    print("  r     : 現在の「幅」を維持したままアスペクト比をリセット（高さを補正）")
    print("  R     : ウィンドウサイズを元のフレームサイズにリセット")
    print("  q or ウィンドウの × : 終了")
    print("起動時は一時停止状態です。")

    while True:
        # ウィンドウが閉じられたかどうか（×ボタン）
        if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
            print("ウィンドウが閉じられました。終了します。")
            break

        if not paused:
            ret, frame = cap.read()
            if not ret:
                print("動画の最後まで再生しました。")
                break
            frame_index += 1

        if frame is not None:
            cv2.imshow(window_name, frame)

        key = cv2.waitKey(30)
        if key == -1:
            continue

        if key == ord("q"):
            print("終了します。")
            break

        elif key == ord(" "):
            paused = not paused
            print("一時停止" if paused else "再生再開")

        elif key == ord("s"):
            if frame is None:
                print("スナップショット失敗: frame が空です。")
                continue

            pos_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
            time_str = format_time_msec(pos_msec)

            base_name = os.path.splitext(os.path.basename(video_path))[0]
            filename = f"{base_name}_{time_str}_{frame_index:06d}.png"
            filepath = os.path.join(output_dir, filename)

            saved = save_frame(filepath, frame)
            if saved:
                print(f"スナップショット保存: {filepath}")
            else:
                print(
                    "スナップショット保存に失敗しました。 "
                    f"shape={getattr(frame, 'shape', None)}, dtype={getattr(frame, 'dtype', None)}"
                )

        elif key == ord("a"):
            # 一時停止中のみ有効: 1 フレーム戻す
            if paused:
                target_index = max(frame_index - 1, 1)
                if target_index == frame_index:
                    continue

                new_cap, new_frame = reopen_and_seek_to_frame(video_path, target_index)
                if new_cap is not None and new_frame is not None:
                    cap.release()
                    cap = new_cap
                    frame = new_frame
                    frame_index = target_index
                    print(f"フレーム戻し: {frame_index}")

        elif key == ord("d"):
            # 一時停止中のみ有効: 1 フレーム進める
            if paused:
                ret, new_frame = cap.read()
                if ret:
                    frame = new_frame
                    frame_index += 1
                    print(f"フレーム送り: {frame_index}")
                else:
                    print("これ以上先のフレームはありません。")

        elif key == ord("r"):
            # 現在の「幅」を維持したまま、アスペクト比だけ補正
            # 現在のウィンドウ幅を取得
            # WND_PROP_AUTOSIZE や他のプロパティではピクセル幅は得られないため、
            # getWindowImageRect を使う（OpenCV 4.5.1 以降）
            try:
                x, y, win_w, win_h = cv2.getWindowImageRect(window_name)
                # 幅を維持し、高さをアスペクト比に合わせて調整
                new_w = win_w
                new_h = int(round(new_w / orig_aspect))
                cv2.resizeWindow(window_name, new_w, new_h)
                print(f"アスペクト比リセット: width={new_w}, height={new_h}")
            except Exception as e:
                print(f"アスペクト比リセットに失敗しました: {e}")

        elif key == ord("R"):
            # ウィンドウサイズを元のフレームサイズにリセット
            cv2.resizeWindow(window_name, orig_width, orig_height)
            print(f"ウィンドウサイズをリセット: width={orig_width}, height={orig_height}")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
