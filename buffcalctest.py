import tkinter as tk
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import math

# 계산 함수
def calculate_apoc2(stat_offset, buff_power_offset, buff_power_mul):
    cases = [
        {"name": "MesugakiCat", "apocConst": 1533, "main_stat": 8599, "buffPower": 237444, "buffPowerAmp": 1.12, "measured": 234799},
        {"name": "MesugakiCatStatAlt", "apocConst": 1533, "main_stat": 8599 - 65, "buffPower": 237444, "buffPowerAmp": 1.12, "measured": 233761},
        {"name": "MesugakiCatBuffAmp1", "apocConst": 1533, "main_stat": 8439, "buffPower": 237444, "buffPowerAmp": 1.12, "measured": 232243},
        {"name": "MesugakiCatBuffAmp2", "apocConst": 1533, "main_stat": 8439, "buffPower": 237444, "buffPowerAmp": 1.05, "measured": 219243},
        {"name": "BedBugLover", "apocConst": 1533, "main_stat": 8233, "buffPower": 230724, "buffPowerAmp": 1.12, "measured": 221958},
        {"name": "DaddyPlease", "apocConst": 1340, "main_stat": 7860, "buffPower": 222514, "buffPowerAmp": 1.12, "measured": 182114},
        {"name": "Papakatsu", "apocConst": 1219, "main_stat": 7340, "buffPower": 208594, "buffPowerAmp": 1.09, "measured": 145182},
    ]

    results = []

    ref = cases[0]
    offset_stat = ref["main_stat"] + stat_offset
    offset_buff = (ref["buffPower"] * ref["buffPowerAmp"] * buff_power_mul + buff_power_offset)
    ref_basic = ref["apocConst"] * ((ref["main_stat"] / 750) + 1)
    X = (ref["measured"] - ref_basic) / (ref["apocConst"] * ((offset_stat / 750) + 1) * offset_buff)

    for case in cases:
        offset_stat = case["main_stat"] + stat_offset
        offset_buff = (case["buffPower"] * ref["buffPowerAmp"] * buff_power_mul + buff_power_offset)
        basic = case["apocConst"] * ((case["main_stat"] / 750) + 1)
        est = case["apocConst"] * ((offset_stat / 750) + 1) * offset_buff * X + basic
        error = est - case["measured"]
        error_percent = (error / case["measured"]) * 100
        results.append(error_percent)

    return results

# 그래프 그리기
def draw_plot(*args):
    try:
        offset_min = float(offset_min_entry.get())
        offset_max = float(offset_max_entry.get())
        mult = buff_mult_slider.get()
    except ValueError:
        return

    offsets = np.linspace(offset_min, offset_max, 50)
    case_names = ["MesugakiCat", "MesugakiCatStatAlt", "MesugakiCatBuffAmp1", "MesugakiCatBuffAmp2", "BedBugLover", "DaddyPlease", "Papakatsu"]
    error_dict = {name: [] for name in case_names}

    for offset in offsets:
        errors = calculate_apoc2(6140, offset, mult)
        for i, name in enumerate(case_names):
            error_dict[name].append(errors[i])

    ax.clear()
    for name in case_names:
        ax.plot(offsets, error_dict[name], label=name)

    ax.axhline(0, color="gray", linestyle="--")
    ax.set_title(f"오차율 변화 (buffPower Offset: {offset_min}~{offset_max}, Mult: {mult:.3f})")
    ax.set_xlabel("buffPower Offset")
    ax.set_ylabel("Error %")
    ax.legend()
    ax.grid(True)

    canvas.draw()

# GUI 구성
root = tk.Tk()
root.title("BuffPower 오차 선그래프")

frame = tk.Frame(root)
frame.pack()

tk.Label(frame, text="buffPower Offset (Min)").grid(row=0, column=0)
offset_min_entry = tk.Entry(frame)
offset_min_entry.insert(0, "-2000")
offset_min_entry.grid(row=0, column=1)

tk.Label(frame, text="buffPower Offset (Max)").grid(row=1, column=0)
offset_max_entry = tk.Entry(frame)
offset_max_entry.insert(0, "2000")
offset_max_entry.grid(row=1, column=1)

tk.Label(frame, text="buffPower Multiply").grid(row=2, column=0)
buff_mult_slider = tk.Scale(frame, from_=0.0001, to=10, resolution=0.001, orient='horizontal', length=2000, command=draw_plot)
buff_mult_slider.set(1.0)
buff_mult_slider.grid(row=2, column=1)

tk.Button(frame, text="업데이트", command=draw_plot).grid(row=3, column=0, columnspan=2, pady=10)

fig, ax = plt.subplots(figsize=(7, 4))
canvas = FigureCanvasTkAgg(fig, master=root)
canvas.get_tk_widget().pack()

draw_plot()
root.mainloop()
