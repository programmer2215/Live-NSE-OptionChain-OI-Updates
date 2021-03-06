import tkcalendar as tkcal 
from datetime import datetime
from ttkwidgets.autocomplete import AutocompleteEntry
import tkinter as tk
from tkinter import ttk
import pyperclip
from matplotlib import pyplot as plt
import matplotlib

matplotlib.use('TkAgg')

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg,
    NavigationToolbar2Tk
)
import threading

from utils.scrape import get_data
from utils.scrape import validate_strike_price

with open(r"./Display/stocks.txt") as f:
    STOCKS = [x.strip() for x in f]

class Display(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.style = ttk.Style()

        self.FONT = ('Helvetice', 14)

        self.style.configure('Treeview', font = self.FONT, rowheight=30)
        self.style.configure('Treeview.Heading', font = self.FONT)
        self.style.configure('my.Radiobutton', font = self.FONT)

        self.font = {
            'font': self.FONT
        }
        
        self.cur_stock_var = tk.StringVar(self)
        self.cur_stock_lab = tk.Label(self, textvariable = self.cur_stock_var, font= self.FONT)
        self.cur_stock_lab.pack(pady=10)
        
        self.last_updated_var = tk.StringVar(self)
        self.last_updated_lab = tk.Label(self, textvariable = self.last_updated_var, font= self.FONT)
        self.last_updated_lab.pack(pady=5)

        self.__columns = ('#1', '#2', '#3')
        self.tree = ttk.Treeview(self, columns=self.__columns, show='headings', selectmode='browse')
        self.tree.column('#1', anchor=tk.CENTER)
        self.tree.column('#2', anchor=tk.CENTER)
        self.tree.column('#3', anchor=tk.CENTER)
        self.tree.heading('#1', text='Strike Prc.')
        self.tree.heading('#2', text='PE OI')
        self.tree.heading('#3', text='CE OI')
        

        self.tree.bind("<Button-3>", self.my_popup)

        self.right_click_menu = tk.Menu(self.tree, tearoff=False)
        self.right_click_menu.add_command(label="Copy Strike Price", command=self.copy_strike_price)
        self.right_click_menu.add_command(label="Remove Strike Price", command=self.remove_strike_price)
        
        self.tree.tag_configure(tagname="green", background="#4feb34")
        self.tree.tag_configure(tagname="red", background="#f03329")

        self.tree.pack(padx=10, pady=10)

        self.frame_controls = tk.Frame(self)
        self.frame_controls.pack(padx=5, pady=10)
        self.expiry_lab = tk.Label(self.frame_controls, text='Last Date', font=self.FONT)
        self.expiry = tkcal.DateEntry(self.frame_controls, selectmode='day')
        self.expiry_lab.grid(row=0, column=1, padx=20, pady=5)
        self.expiry.grid(row=1, column=1, padx=20, pady=5)

        
        
        self.script_label = ttk.Label(self.frame_controls, text="Script", **self.font)
        self.script_var = tk.StringVar(self.frame_controls, value="NIFTY")
        self.script_entry = AutocompleteEntry(self.frame_controls, textvariable=self.script_var, width=10, completevalues=STOCKS,font=self.FONT)
        self.script_label.grid(row=0, column=0,pady=6, padx=30)
        self.script_entry.grid(row=1, column=0,pady=2, padx=30)  

        self.delay_label = ttk.Label(self.frame_controls, text="Delay (Mins)", **self.font)
        self.delay_var = tk.StringVar(value="5")
        self.delay_input = ttk.Entry(self.frame_controls, textvariable=self.delay_var, width=8)
        self.delay_label.grid(row=0, column=2,pady=6, padx=30)
        self.delay_input.grid(column=2, row=1, padx=2)

        self.strike_price_lab = ttk.Label(self.frame_controls, text="Strike Price Filter", font = ('Helvetice', 16, 'bold'))
        self.strike_price_lab.grid(row=2, column=0, columnspan=4, pady=12, padx=30)

        self.strike_price_label = ttk.Label(self.frame_controls, text="Strike Price", **self.font)
        self.strike_price_var = tk.StringVar(self.frame_controls)
        self.strike_price_input = ttk.Entry(self.frame_controls, textvariable=self.strike_price_var, width=8, font=self.FONT)
        self.strike_price_label.grid(row=3, column=0, columnspan=2, pady=6, padx=30)
        self.strike_price_input.grid(row=4, column=0, columnspan=2, padx=2)
        self.strike_price_watchlist = list()

        self.filter_btn = ttk.Button(self.frame_controls, text="Add", command=self.add_strike_price)
        self.filter_btn.grid(column=1, row=3, columnspan=3, rowspan=2, padx=2)
        
        self.update_btn = ttk.Button(self.frame_controls, text="Update Info", command=self.manual_update)
        self.update_btn.grid(column=3, row=0, rowspan=2, padx=2)

         # prepare data
        self.data = {
            'SCRIPT': "NIFTY",
            'CE_TOTAL' : 0,
            'PE_TOTAL' : 0,
            'PE': 0,
            'CE': 0
        }
        self.prev_data = {
            'SCRIPT': "NIFTY",
            'CE_TOTAL' : 0,
            'PE_TOTAL' : 0,
            'PE': 0,
            'CE': 0
        }
        options = ('CE','PE')
        total_OI = (self.data['CE_TOTAL'], self.data['PE_TOTAL'])

        # create a figure
        self.figure = Figure(figsize=(6, 3), dpi=100)

        # create FigureCanvasTkAgg object
        self.figure_canvas = FigureCanvasTkAgg(self.figure, self.parent)

        # create the toolbar
        NavigationToolbar2Tk(self.figure_canvas, self.parent)

        # create axes
        self.axes = self.figure.add_subplot()

        # create the barchart
        self.axes.bar(options, total_OI)
        self.axes.set_title('Total OI')
        self.axes.set_ylabel('OI')

        self.figure_canvas.get_tk_widget().pack(padx=10,side=tk.RIGHT, fill=tk.BOTH, expand=1)
        self.stats_frame = tk.Frame(self)
        self.stats_frame.pack()
        self.OI_diff_percent_var = tk.StringVar(self)
        self.OI_diff_percent_lab = tk.Label(self.stats_frame, textvariable = self.OI_diff_percent_var, font= ('Helvetice', 15, 'bold'))
        self.OI_diff_percent_lab.grid(row=0, column=0, padx=5, pady=5)

        self.prev_OI_diff_percent_var = tk.StringVar(self)
        self.prev_OI_diff_percent_lab = tk.Label(self.stats_frame, textvariable = self.prev_OI_diff_percent_var, font= ('Helvetice', 15, 'bold'))
        self.prev_OI_diff_percent_lab.grid(row=1, column=0, padx=5, pady=5)

        self.CE_OI_percent_var = tk.StringVar(self)
        self.CE_OI_percent_lab = tk.Label(self.stats_frame, textvariable = self.CE_OI_percent_var, font= ('Helvetice', 15, 'bold'))
        self.CE_OI_percent_lab.grid(row=0, column=1, padx=5, pady=5)

        self.PE_OI_percent_var = tk.StringVar(self)
        self.PE_OI_percent_lab = tk.Label(self.stats_frame, textvariable = self.PE_OI_percent_var, font= ('Helvetice', 15, 'bold'))
        self.PE_OI_percent_lab.grid(row=1, column=1, padx=5, pady=5)


    def manual_update(self):
        if len(threading.enumerate()) < 2:
            self.load_data()
        else: print("thread busy")
    
    def __addlabels(self, x, y):
        for i in range(len(x)):
            plt.text(i, y[i], y[i], ha = 'center')
    
    def add_strike_price(self):
        strike_price = self.strike_price_var.get().strip()
        if not strike_price.isnumeric():
            print('Invalid Strike Price')
            return
        strike_price = int(strike_price)
        date = datetime.strftime(self.expiry.get_date(), '%d-%b-%Y')
        stock_name = self.script_var.get().strip()
        if strike_price not in self.strike_price_watchlist:
            if validate_strike_price(date, stock_name, strike_price):
                self.strike_price_watchlist.append(strike_price)
                self.manual_update()

    def load_data(self):
        now = datetime.now().strftime("%H:%M:%S")
        print(f"[REFRESH TIME] {now}")
        date = datetime.strftime(self.expiry.get_date(), '%d-%b-%Y')
        stock_name = self.script_var.get().strip()
        raw_data = get_data(date, stock_name)
        data = raw_data[0]
        if data is None:
            return
        data_main = sorted(data, key=lambda i: i['PE OI'], reverse=True)[:1] + sorted(data, key=lambda i: i['CE OI'], reverse=True)[:1]
        if len(data_main) > 1:
            for i in self.tree.get_children():
                self.tree.delete(i)
            for i in range(len(data_main)):
                vals = tuple(data_main[i].values())
                if vals[0] in self.strike_price_watchlist:
                    self.strike_price_watchlist.remove(vals[0])
                self.tree.insert("", tk.END, iid=i, value=vals)
            if stock_name == self.prev_data['SCRIPT']:
                for strikePrice in self.strike_price_watchlist:
                    strike_price_data = get_data(date, stock_name, _filter=True, strike_price=strikePrice)
                    self.tree.insert("", tk.END, value=(strikePrice, strike_price_data['PE OI'], strike_price_data['CE OI']))
            else:
                self.strike_price_watchlist = []

            
            self.data = raw_data[1]
            self.data['PE'] = data_main[0]['PE OI']
            self.data['CE'] = data_main[0]['CE OI']
            self.data['SCRIPT'] = stock_name
            
            options = ('CE','PE')
            total_OI = (self.data['CE_TOTAL'], self.data['PE_TOTAL'])
            print(total_OI)
            tot_diff = (self.data["CE_TOTAL"] - self.data["PE_TOTAL"])
            tot_diff_per = round((tot_diff / self.data["CE_TOTAL"]) * 100, 2)
            
            self.OI_diff_percent_var.set(f"OI Diff: {tot_diff_per}%")
            if tot_diff_per > 0:
                self.OI_diff_percent_lab.config(fg="green")
            else:
                self.OI_diff_percent_lab.config(fg="red")
            try:
                if self.data['SCRIPT'] == self.prev_data['SCRIPT']:
                    tot_prev_diff = (self.prev_data["CE_TOTAL"] - self.prev_data["PE_TOTAL"])
                    tot_prev_diff_per = round(((tot_diff - tot_prev_diff) / tot_prev_diff) * 100, 2)
                    self.prev_OI_diff_percent_var.set(f"OI Diff prev: {tot_prev_diff_per}%")

                    if tot_prev_diff_per > 0:
                        self.prev_OI_diff_percent_lab.config(fg="green")
                    else:
                        self.prev_OI_diff_percent_lab.config(fg="red")
                else:
                    self.prev_OI_diff_percent_var.set(f"OI Diff prev: 0%")
                    self.prev_OI_diff_percent_lab.config(fg="black")
            except ZeroDivisionError:
                self.prev_OI_diff_percent_var.set(f"OI Diff prev: 0%")
                self.prev_OI_diff_percent_lab.config(fg="black")

            # CE OI DIFF
            try:
                if self.data['SCRIPT'] == self.prev_data['SCRIPT']:
                    ce_diff = self.data['CE'] - self.prev_data['CE']
                    ce_diff_per = round((ce_diff / self.prev_data['CE']) * 100, 2)
                    self.CE_OI_percent_var.set(f"CE Diff: {ce_diff_per}%")
                    if ce_diff_per > 0:
                        self.CE_OI_percent_lab.config(fg="green")
                    else:
                        self.CE_OI_percent_lab.config(fg="red")
                else:
                    self.CE_OI_percent_var.set(f"CE Diff: 0%")
                    self.CE_OI_percent_lab.config(fg="black")
            except ZeroDivisionError:
                self.CE_OI_percent_var.set(f"CE Diff: 0%")
                self.CE_OI_percent_lab.config(fg="black")
            # PE OI DIFF
            try:
                if self.data['SCRIPT'] == self.prev_data['SCRIPT']:
                    pe_diff = self.data['PE'] - self.prev_data['PE']
                    pe_diff_per = round((pe_diff / self.prev_data['PE']) * 100, 2)
                    self.PE_OI_percent_var.set(f"PE Diff: {pe_diff_per}%")
                    if pe_diff_per > 0:
                        self.PE_OI_percent_lab.config(fg="green")
                    else:
                        self.PE_OI_percent_lab.config(fg="red")
                else:
                    self.PE_OI_percent_var.set(f"PE Diff: 0%")
                    self.PE_OI_percent_lab.config(fg="black")
            except ZeroDivisionError:
                self.PE_OI_percent_var.set(f"PE Diff: 0%")
                self.PE_OI_percent_lab.config(fg="black")

            self.axes.clear()
            self.axes.bar(options, total_OI, color=["green", "red"])
            self.axes.set_title(stock_name)
            self.axes.set_ylabel('OI')
            
            self.figure.canvas.draw()
            self.__addlabels(list(options), list(total_OI))
            self.parent.update()
            self.figure.canvas.draw()
            self.figure.canvas.flush_events()
            self.cur_stock_var.set("Current Stock: " + stock_name)
            now = datetime.now().strftime("%H:%M:%S")
            self.last_updated_var.set("Last Updated: " + now)

            self.prev_data = self.data.copy()
    
    def refresh(self):
        self.t1 = threading.Thread(target=self.load_data, daemon=True)
        self.t1.start()
        delay = int(float(self.delay_var.get()) * 60 * 1000)
        self.parent.after(delay, self.refresh)
    
    def copy_strike_price(self):
            cur_row = self.tree.focus()
            pyperclip.copy(self.tree.item(cur_row)['values'][0])

    def remove_strike_price(self):
        cur_row = self.tree.focus()
        price = self.tree.item(cur_row)['values'][0]
        self.strike_price_watchlist.remove(price)
        self.manual_update()

    def my_popup(self, e):
        self.right_click_menu.tk_popup(e.x_root, e.y_root)
'''root = tk.Tk()
a = Display(root)
a.pack(side="top", fill="both", expand=True)
a.refresh()

root.mainloop()'''
