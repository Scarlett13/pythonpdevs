"""
This visual DEVS plotter is based on Bill Song's DEVS Visual Modeling and Simulation Environment,
however, it has been ported to the PythonPDEVS logic.

See Also:
	`http://msdl.uantwerpen.be/people/bill/devsenv/summerpresentation.pdf`_
"""

import tkinter as tk
from tkinter import ttk
from tkinter import filedialog as fd

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, ArrowStyle
import matplotlib.animation as animation
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import numpy as np
import pandas as pd

import dataclasses
import xml.etree.ElementTree as ET


def is_float(val):
		try:
			float(val)
		except ValueError:
			return False
		else:
			return True


class Window:
	def __init__(self):
		self.root = tk.Tk()

		# self.filename = fd.askopenfilename(parent=self.root, title="Open an XML trace file",
		#                                    initialdir=r"C:\Users\randy\AppData\Roaming\JetBrains\PyCharm2023.3\scratches",
		#                                    filetypes=[("XML files", "*.xml")])
		# if not self.filename:
		# 	self.root.quit()

		self.filename = r"C:\Users\randy\AppData\Roaming\JetBrains\PyCharm2023.3\scratches\test.xml"

		self.time = 0.0
		self.active_model = ""
		self.active_state = ""

		# load in the model
		self.trace_state = pd.DataFrame(columns=['time', 'model', 'kind', 'path', 'value'])
		self.parse_trace_file()

		self.make_gui()
		self._build_tree(pd.unique(self.trace_state["model"]), self.mtree)

		self.update()
		self.root.mainloop()

	def make_gui(self):
		self.root.title("DEVS XML Plotting Environment - %s" % self.filename)

		self.frame = ttk.Frame(self.root, padding=10)
		self.frame.pack(fill=tk.BOTH, expand=True)

		self.toolbar = ttk.Frame(self.frame)
		self.toolbar.pack(side=tk.TOP, fill=tk.X)

		self.container = ttk.Frame(self.frame)
		self.container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
		self.trees = ttk.Frame(self.container)
		self.trees.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

		self.button_first = ttk.Button(self.toolbar, text="<<", command=self.to_first)
		self.button_first.pack(side=tk.LEFT)
		self.button_prev = ttk.Button(self.toolbar, text="<", command=self.to_prev)
		self.button_prev.pack(side=tk.LEFT)
		self.button_next = ttk.Button(self.toolbar, text=">", command=self.to_next)
		self.button_next.pack(side=tk.LEFT)
		self.button_last = ttk.Button(self.toolbar, text=">>", command=self.to_last)
		self.button_last.pack(side=tk.LEFT)
		# sep = ttk.Separator(self.toolbar)
		# sep.pack(side=tk.LEFT)
		lbl_window = ttk.Label(self.toolbar, text="   Window Size: ")
		lbl_window.pack(side=tk.LEFT)
		self.window_size = ttk.Spinbox(self.toolbar, from_=0, to=50)
		self.window_size.set(10)
		self.window_size.pack(side=tk.LEFT)

		self.mtree = ttk.Treeview(self.trees, selectmode="browse", columns=["path"], displaycolumns=[])
		self.mtree.heading('#0', text="Select a Model:", anchor=tk.W)
		self.mtree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
		self.mtree.bind("<<TreeviewSelect>>", self.select_in_mtree)

		self.stree = ttk.Treeview(self.trees, selectmode="browse", columns=["path"], displaycolumns=[])
		self.stree.heading('#0', text="Plottable Attributes:", anchor=tk.W)
		self.stree.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)
		self.stree.pack_forget()
		self.stree.bind("<<TreeviewSelect>>", self.select_in_stree)

		self.figure = plt.figure(dpi=100)
		self.figure.tight_layout()
		self.axis = self.figure.add_subplot(111)
		self.axis.set_xlabel("time")
		self.axis.set_ylim((0, 1))
		self.canvas = FigureCanvasTkAgg(self.figure, master=self.container)
		self.canvas.draw()
		self.canvas.get_tk_widget().pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
		self.__cursor, = self.axis.plot([0, 0], [0, 0], '--', c='b', alpha=0.7)
		self.__line, = self.axis.plot([], [], '-o', c='g', mec='r', fillstyle='none')
		self.__idots, = self.axis.plot([], [], 'o', c='g')
		self.__edots, = self.axis.plot([], [], 'o', c='r')
		self.__arrows = []
		self.__ani = animation.FuncAnimation(self.figure, lambda _: self.update(), interval=100)

		self.output = tk.Text(self.frame, height=7)
		self.output.pack(side=tk.BOTTOM, fill=tk.X, expand=True)
		self.output.pack_forget()

	def to_first(self):
		if self.active_model != "" and self.active_state != "":
			self.time = 0.0

	def to_prev(self):
		if self.active_model != "" and self.active_state != "":
			event_list = self.trace_state[(self.trace_state["model"] == self.active_model) &
										  (self.trace_state["path"] == self.active_state)]
			earlier = event_list[event_list["time"] < self.time]
			if len(earlier) > 0:
				self.time = earlier.iloc[-1]["time"]

	def to_next(self):
		if self.active_model != "" and self.active_state != "":
			event_list = self.trace_state[(self.trace_state["model"] == self.active_model) &
										  (self.trace_state["path"] == self.active_state)]
			later = event_list[event_list["time"] > self.time]
			if len(later) > 0:
				self.time = later.iloc[0]["time"]

	def to_last(self):
		if self.active_model != "" and self.active_state != "":
			event_list = self.trace_state[(self.trace_state["model"] == self.active_model) &
										  (self.trace_state["path"] == self.active_state)]
			if len(event_list) > 0:
				self.time = event_list.iloc[-1]["time"]

	def get_window(self):
		return int(self.window_size.get())

	def _flatten_dict(self, data):
		res = {}
		for k, v in data.items():
			if isinstance(v, dict):
				dct = self._flatten_dict(v)
				for kk, vv in dct.items():
					res[k + "." + kk] = vv
			else:
				res[k] = v
		return res

	def parse_trace_file(self):
		tree = ET.parse(self.filename)
		root = tree.getroot()

		for item in root.findall('event'):
			model = item.find("model").text
			attrs = self._flatten_dict(self._parse_attributes(item.find("state")))
			time = float(item.find("time").text)
			kind = item.find("kind").text

			rows = []
			for key, v in attrs.items():
				rows.append([time, model, kind, key, v])
			self.trace_state = pd.concat([self.trace_state, pd.DataFrame(rows, columns=self.trace_state.columns)],
										 ignore_index=True)
		self.trace_state = self.trace_state.sort_values(by="time")

	def _parse_attributes(self, node):
		res = {}
		for attr in node.findall('attribute'):
			name = attr.find("name").text
			valueN = attr.find("value")
			typ = attr.find("type").text
			if len(valueN.findall("attribute")) > 0:
				res[name] = self._parse_attributes(valueN)
			else:
				if attr.attrib["category"] == "P":
					if typ == "Integer":
						res[name] = int(valueN.text)
					elif typ == "Float":
						res[name] = float(valueN.text)
					elif typ == "Boolean":
						res[name] = valueN.text == "True"
					else:  # String
						res[name] = valueN.text
				else:
					res[name] = valueN.text
		return res

	def _build_tree(self, paths, tree):
		ix = 0
		tree_ids = {}
		for model in paths:
			lst = model.split(".")
			for mix in range(len(lst)):
				parent = ".".join(lst[:mix])
				path = ".".join(lst[:mix + 1])
				if path not in tree_ids:
					tree.insert(tree_ids.get(parent, ''), tk.END, ix, text=lst[mix], open=True, values=[path])
					tree_ids[path] = ix
					ix += 1

	def update(self):
		if self.active_model != "" and self.active_state != "":
			self.create_plot_for_active_model_state()
			self.output.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)
			self.output.delete("1.0", tk.END)
			event_list = self.trace_state[(self.trace_state["model"] == self.active_model) &
			                              (self.trace_state["path"] == self.active_state) &
			                              (self.trace_state["time"] == self.time)]
			next_evts = self.trace_state[(self.trace_state["model"] == self.active_model) &
			                 (self.trace_state["path"] == self.active_state) &
			                 (self.trace_state["time"] > self.time)]
			if len(next_evts) > 0:
				next_time = next_evts.iloc[0]["time"]
			else:
				next_time = "N/A"

			for eidx, event in event_list.iterrows():
				self.output.insert(tk.END, "TIME: %.4f\nSTATE: %s\n" % (self.time, str(event["value"])))
				if event["kind"] == "IN":
					self.output.insert(tk.END, 'Internal Transition:\n')
					# self.output.insert(tk.END, "  Port: %s\n" % )
					self.output.insert(tk.END, "  Time Next: %s" % next_time)
				elif event["kind"] == "EX":
					self.output.insert(tk.END, 'External Transition')
				else:
					self.output.insert(tk.END, 'Undefined Transition')

			# tam = self.trace[self.active_model]
			# for ix, ev in enumerate(tam):
			# 	if ev["time"] == self.time:
			# 		state = ev["state"]
			# 		for p in self.active_state.split("."):
			# 			state = state[p]
			# 		self.output.insert(tk.END, "TIME: %.4f\nSTATE: %s\n" % (self.time, str(state)))
			# 		if ev["kind"] == "IN":
			# 			self.output.insert(tk.END, 'Internal Transition:\n  Port: %s\n  Output: %s\n  Time Next: %.4f' %
			# 			                   (ev["port"]["name"], ev["port"]["message"], tam[ix + 1]["time"] if ix + 1 < len(tam) else "N/A"))
			# 		elif ev["kind"] == "EX":
			# 			if "port" in ev:
			# 				self.output.insert(tk.END,
			# 				                   'External Transition:\n  Port: %s\n  Input: %s\n  Time Next: %.4f' %
			# 				                   (ev["port"]["name"], ev["port"]["message"],
			# 				                    tam[ix + 1]["time"] if ix + 1 < len(tam) else "N/A"))
			# 			else:
			# 				self.output.insert(tk.END, 'External Transition')
			# 		else:
			# 			self.output.insert(tk.END, 'Undefined Transition')
			# 		break

		else:
			self.clear_plot()

	def select_in_mtree(self, event):
		self.clear_plot()
		tree = event.widget
		selection = [tree.item(item)["values"][0] for item in tree.selection() if len(tree.get_children(item)) == 0]
		if len(selection) == 1:
			self.active_model = selection[0]
			self.stree.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)
			if len(self.stree.get_children()) > 0:
				self.stree.delete(self.stree.get_children())
			self._build_tree(pd.unique(self.trace_state[self.trace_state["model"] == self.active_model]["path"]),
							 self.stree)
		else:
			self.active_model = ""
			self.stree.pack_forget()
		self.active_state = ""

	def select_in_stree(self, event):
		tree = event.widget
		selection = [tree.item(item)["values"][0] for item in tree.selection() if len(tree.get_children(item)) == 0]
		if len(selection) == 1:
			self.clear_plot()
			self.active_state = selection[0]

	def create_arrow(self, x, y, dx, dy):
		if dy < 0:
			style = "angle,angleA=45,angleB=-45,rad=15"
		elif dy > 0:
			style = "angle,angleA=-45,angleB=45,rad=15"
		else:
			style = "arc,angleA=135,angleB=45,armA=20,armB=20,rad=15"
		return FancyArrowPatch((x, y), (x + dx, y + dy),
		                       connectionstyle=style,
		                       shrinkA=1, shrinkB=1, zorder=10, color='black',
		                       arrowstyle=ArrowStyle.CurveFilledB(head_width=3, head_length=5))

	def clear_plot(self):
		self.__line.set_data([], [])
		self.__idots.set_data([], [])
		self.__edots.set_data([], [])
		for a in self.__arrows:
			a.remove()
		self.__arrows.clear()
		self.axis.set_title("")
		self.axis.set_xlim((0, 1))
		self.axis.set_ylim((-0.5, 0.5))
		self.axis.set_yticks([])
		self.axis.set_yticklabels([])

	def create_plot_for_active_model_state(self):
		self.axis.set_title("%s: %s" % (self.active_model, self.active_state))

		event_list = self.trace_state[(self.trace_state["model"] == self.active_model) &
									  (self.trace_state["path"] == self.active_state)]

		mid = self.time
		ws = self.get_window()
		lower = max(mid - ws / 2, 0.0)
		upper = lower + ws

		event_list_lowest = lower
		event_list_lower = event_list[event_list["time"] < lower]
		if len(event_list_lower) > 0:
			event_list_lowest = event_list_lower.iloc[-1]["time"]
		event_list_highest = upper
		event_list_upper = event_list[event_list["time"] > upper]
		if len(event_list_upper) > 0:
			event_list_highest = event_list_upper.iloc[0]["time"]
		event_list = event_list[event_list["time"].between(event_list_lowest, event_list_highest)]

		times = event_list["time"]
		lower = max(times.min(), lower)
		upper = min(times.max(), upper)

		in_times = event_list[event_list["kind"] == "IN"]["time"].to_numpy()
		in_evts = event_list[event_list["kind"] == "IN"]["value"].to_numpy()
		out_times = event_list[event_list["kind"] == "EX"]["time"].to_numpy()
		out_evts = event_list[event_list["kind"] == "EX"]["value"].to_numpy()

		ts = times.repeat(3).iloc[2:-2].to_numpy()
		vs = event_list["value"].iloc[:-1].repeat(2).to_numpy()
		vs = np.insert(vs, [x for x in range(2, len(vs), 2)], np.nan)
		times = times.to_numpy()
		state_sets = np.sort(event_list["value"].unique(), kind='mergesort')
		min_ = np.nanmin(vs)
		max_ = np.nanmax(vs)

		if len(times) < 20:
			self.axis.set_xticks(times)
		else:
			self.axis.set_xticks([times.min(), times.max()])
		if len(state_sets) < 20:
			if np.all(np.vectorize(is_float, otypes=[bool])(state_sets)):
				self.axis.set_yticks(state_sets)
				self.axis.set_yticklabels(state_sets)
			else:
				self.axis.set_yticks(range(len(state_sets)))
				self.axis.set_yticklabels(state_sets)
		else:
			self.axis.set_yticks([min_, max_])
			self.axis.set_yticklabels([min_, max_])

		self.axis.set_xlim((lower, upper))
		self.axis.set_ylim((min_ - 0.5, max_ + 0.5))

		self.__cursor.set_data([mid, mid], [min_ - 0.5, max_ + 0.5])
		self.__line.set_data(ts, vs)
		self.__idots.set_data(in_times, in_evts)
		self.__edots.set_data(out_times, out_evts)

		for i in range(len(ts) // 3):
			ix = i * 3 + 1
			iy = (i + 1) * 3
			if i >= len(self.__arrows):
				arrow = self.create_arrow(ts[ix], vs[ix], 0, vs[iy] - vs[ix])
				self.__arrows.append(arrow)
				self.axis.add_patch(arrow)
			else:
				self.__arrows[i].set_positions((ts[ix], vs[ix]), (ts[iy], vs[iy]))

		while len(self.__arrows) > (len(ts) // 3):
			self.__arrows.pop().remove()



if __name__ == '__main__':
	Window()