#!/usr/bin/env python3
"""
Valley Finder - 能量谷底查找算法

用于在音频波形中搜索能量最低点（谷底），作为剪辑的剪切点。
"""

import numpy as np
from typing import Tuple, Optional


def calc_energy(wav: np.ndarray, start_idx: int, window_size: int) -> float:
    """计算指定窗口的 RMS 能量"""
    end_idx = min(start_idx + window_size, len(wav))
    if end_idx <= start_idx:
        return 0.0
    chunk = wav[start_idx:end_idx]
    return float(np.sqrt(np.mean(chunk ** 2)))


def find_energy_valley(
    wav: np.ndarray,
    sample_rate: int,
    center_time: float,
    search_ms: int = 100,
    direction: str = "left"
) -> Tuple[float, float]:
    """
    在时间点附近搜索能量最低点（谷底）

    Args:
        wav: 音频波形数据
        sample_rate: 采样率
        center_time: 中心时间（秒）
        search_ms: 搜索范围（毫秒）
        direction: 搜索方向："left" 向左搜索，"right" 向右搜索

    Returns:
        (best_time, energy_ratio) 最佳位置和能量比值
    """
    center_idx = int(center_time * sample_rate)
    search_samples = int(search_ms / 1000 * sample_rate)
    window_size = int(0.02 * sample_rate)  # 20ms 窗口

    if direction == "left":
        start_idx = max(0, center_idx - search_samples)
        end_idx = center_idx
        step = int(0.005 * sample_rate)  # 5ms 步进
    else:  # right
        start_idx = center_idx
        end_idx = min(len(wav), center_idx + search_samples)
        step = int(0.005 * sample_rate)

    if end_idx - start_idx < window_size:
        return center_time, 1.0

    # 计算搜索范围内的最大能量（用于归一化）
    max_energy = 0.0
    for i in range(start_idx, end_idx - window_size, step):
        energy = calc_energy(wav, i, window_size)
        if energy > max_energy:
            max_energy = energy

    if max_energy == 0:
        return center_time, 0.0

    # 找到能量最低点
    min_energy = float('inf')
    best_idx = center_idx
    for i in range(start_idx, end_idx - window_size, step):
        energy = calc_energy(wav, i, window_size)
        if energy < min_energy:
            min_energy = energy
            best_idx = i

    energy_ratio = min_energy / max_energy
    best_time = best_idx / sample_rate

    return best_time, energy_ratio


def find_valley_boundaries(
    wav: np.ndarray,
    sample_rate: int,
    word_start_time: float,
    word_end_time: float,
    left_search_ms: int = 100,
    right_search_ms: int = 100,
    threshold: float = 0.7
) -> dict:
    """
    找到字词边界附近的能量谷底作为剪切点

    Args:
        wav: 音频波形数据
        sample_rate: 采样率
        word_start_time: 第一个字的开始时间
        word_end_time: 最后一个字的结束时间
        left_search_ms: 向左搜索的范围（毫秒）
        right_search_ms: 向右搜索的范围（毫秒）
        threshold: 能量比阈值，超过则警告

    Returns:
        {
            "cut_start": 修正后的开始时间，
            "cut_end": 修正后的结束时间，
            "left_ratio": 左边界能量比，
            "right_ratio": 右边界能量比，
            "quality": 质量评估 ("good" | "fair" | "poor"),
            "warning": 警告信息（如果有）
        }
    """
    # 搜索左边界谷底（向左搜索，即从 word_start_time 往前找）
    left_cut, left_ratio = find_energy_valley(
        wav, sample_rate, word_start_time, left_search_ms, direction="left"
    )

    # 搜索右边界谷底（向右搜索，即从 word_end_time 往后找）
    right_cut, right_ratio = find_energy_valley(
        wav, sample_rate, word_end_time, right_search_ms, direction="right"
    )

    # 评估质量
    max_ratio = max(left_ratio, right_ratio)
    if max_ratio < 0.3:
        quality = "good"
        warning = None
    elif max_ratio < threshold:
        quality = "fair"
        warning = f"边界能量比较高 (左={left_ratio:.2f}, 右={right_ratio:.2f})，剪切可能有轻微爆音"
    else:
        quality = "poor"
        warning = f"警告：边界不在能量谷底 (左={left_ratio:.2f}, 右={right_ratio:.2f})，剪切可能有明显爆音"

    return {
        "cut_start": float(left_cut),
        "cut_end": float(right_cut),
        "left_ratio": float(left_ratio),
        "right_ratio": float(right_ratio),
        "quality": quality,
        "warning": warning,
    }


def load_audio_for_valley(audio_path: str) -> Tuple[np.ndarray, int]:
    """加载音频用于能量分析"""
    import soundfile as sf
    wav, sr = sf.read(audio_path)
    if wav.ndim > 1:
        wav = np.mean(wav, axis=1)
    return wav, sr
