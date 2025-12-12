
### config=baseline, strategy=priority ###

set terminal svg size 1200 900

# plot 1. x-axis: products, y-axis: flow time of product

set out 'plot_products_baseline_priority.svg'
set title "Flow Time (config=baseline, strategy=priority)"
set xlabel "Product #"
set ylabel "Minutes"
set key title "Max Wait (min)"
set key bottom center out
set key horizontal

# set yrange [0:90]
set xrange [0:500]
set style fill solid

plot 'output_baseline_priority.csv' \
    using 1:2 title '0' w boxes ls 1, \
 '' using 1:3 title '3' w boxes ls 2, \
 '' using 1:4 title '6' w boxes ls 3


### config=add-new-machines, strategy=priority ###

set terminal svg size 1200 900

# plot 1. x-axis: products, y-axis: flow time of product

set out 'plot_products_add-new-machines_priority.svg'
set title "Flow Time (config=add-new-machines, strategy=priority)"
set xlabel "Product #"
set ylabel "Minutes"
set key title "Max Wait (min)"
set key bottom center out
set key horizontal

# set yrange [0:90]
set xrange [0:500]
set style fill solid

plot 'output_add-new-machines_priority.csv' \
    using 1:2 title '0' w boxes ls 1, \
 '' using 1:3 title '3' w boxes ls 2, \
 '' using 1:4 title '6' w boxes ls 3


### config=double-capacity, strategy=priority ###

set terminal svg size 1200 900

# plot 1. x-axis: products, y-axis: flow time of product

set out 'plot_products_double-capacity_priority.svg'
set title "Flow Time (config=double-capacity, strategy=priority)"
set xlabel "Product #"
set ylabel "Minutes"
set key title "Max Wait (min)"
set key bottom center out
set key horizontal

# set yrange [0:90]
set xrange [0:500]
set style fill solid

plot 'output_double-capacity_priority.csv' \
    using 1:2 title '0' w boxes ls 1, \
 '' using 1:3 title '3' w boxes ls 2, \
 '' using 1:4 title '6' w boxes ls 3


### config=double-speed, strategy=priority ###

set terminal svg size 1200 900

# plot 1. x-axis: products, y-axis: flow time of product

set out 'plot_products_double-speed_priority.svg'
set title "Flow Time (config=double-speed, strategy=priority)"
set xlabel "Product #"
set ylabel "Minutes"
set key title "Max Wait (min)"
set key bottom center out
set key horizontal

# set yrange [0:90]
set xrange [0:500]
set style fill solid

plot 'output_double-speed_priority.csv' \
    using 1:2 title '0' w boxes ls 1, \
 '' using 1:3 title '3' w boxes ls 2, \
 '' using 1:4 title '6' w boxes ls 3

# plot 2. x-axis: max-wait parameter, y-axis: flow times of products

set out 'plot_box_baseline_priority.svg'
set title "Flow Time Distribution (config=baseline, strategy=priority)"
set style fill solid 0.25 border -1
set style boxplot outliers pointtype 7
set style data boxplot
set key off

set xlabel "Max Wait (minutes)"
unset xrange
unset yrange

set xtics ('0' 0, '3' 1, '6' 2)

plot 'output_baseline_priority.csv' \
    using (0):2 title '0', \
  '' using (1):3 title '3', \
  '' using (2):4 title '6'



# plot 2. x-axis: max-wait parameter, y-axis: flow times of products

set out 'plot_box_add-new-machines_priority.svg'
set title "Flow Time Distribution (config=add-new-machines, strategy=priority)"
set style fill solid 0.25 border -1
set style boxplot outliers pointtype 7
set style data boxplot
set key off

set xlabel "Max Wait (minutes)"
unset xrange
unset yrange

set xtics ('0' 0, '3' 1, '6' 2)

plot 'output_add-new-machines_priority.csv' \
    using (0):2 title '0', \
  '' using (1):3 title '3', \
  '' using (2):4 title '6'



# plot 2. x-axis: max-wait parameter, y-axis: flow times of products

set out 'plot_box_double-capacity_priority.svg'
set title "Flow Time Distribution (config=double-capacity, strategy=priority)"
set style fill solid 0.25 border -1
set style boxplot outliers pointtype 7
set style data boxplot
set key off

set xlabel "Max Wait (minutes)"
unset xrange
unset yrange

set xtics ('0' 0, '3' 1, '6' 2)

plot 'output_double-capacity_priority.csv' \
    using (0):2 title '0', \
  '' using (1):3 title '3', \
  '' using (2):4 title '6'



# plot 2. x-axis: max-wait parameter, y-axis: flow times of products

set out 'plot_box_double-speed_priority.svg'
set title "Flow Time Distribution (config=double-speed, strategy=priority)"
set style fill solid 0.25 border -1
set style boxplot outliers pointtype 7
set style data boxplot
set key off

set xlabel "Max Wait (minutes)"
unset xrange
unset yrange

set xtics ('0' 0, '3' 1, '6' 2)

plot 'output_double-speed_priority.csv' \
    using (0):2 title '0', \
  '' using (1):3 title '3', \
  '' using (2):4 title '6'

# plot 3. x-axis: flow time interval, y-axis: number of products

bin_width = 5;  # 5 minutes

set out 'plot_freq_baseline_priority.svg'
set title "Frequency of flow times (config=baseline, strategy=priority)"
set boxwidth (bin_width) absolute
set style fill solid 1.0 noborder

set key title "Max Wait (min)"
set key bottom center out
# set key horizontal

set xtics auto
set xrange [0:]
set xlabel "Flow Time (minutes, interval)"
set ylabel "Number of products"

bin_number(x) = floor(x/bin_width)
rounded(x) = bin_width * ( bin_number(x) + 0.5 )

plot 'output_baseline_priority.csv' \
    using (rounded($2)):(1) title '0' smooth frequency with boxes, \
 '' using (rounded($3)):(1) title '3' smooth frequency with boxes, \
 '' using (rounded($4)):(1) title '6' smooth frequency with boxes



# plot 3. x-axis: flow time interval, y-axis: number of products

bin_width = 5;  # 5 minutes

set out 'plot_freq_add-new-machines_priority.svg'
set title "Frequency of flow times (config=add-new-machines, strategy=priority)"
set boxwidth (bin_width) absolute
set style fill solid 1.0 noborder

set key title "Max Wait (min)"
set key bottom center out
# set key horizontal

set xtics auto
set xrange [0:]
set xlabel "Flow Time (minutes, interval)"
set ylabel "Number of products"

bin_number(x) = floor(x/bin_width)
rounded(x) = bin_width * ( bin_number(x) + 0.5 )

plot 'output_add-new-machines_priority.csv' \
    using (rounded($2)):(1) title '0' smooth frequency with boxes, \
 '' using (rounded($3)):(1) title '3' smooth frequency with boxes, \
 '' using (rounded($4)):(1) title '6' smooth frequency with boxes



# plot 3. x-axis: flow time interval, y-axis: number of products

bin_width = 5;  # 5 minutes

set out 'plot_freq_double-capacity_priority.svg'
set title "Frequency of flow times (config=double-capacity, strategy=priority)"
set boxwidth (bin_width) absolute
set style fill solid 1.0 noborder

set key title "Max Wait (min)"
set key bottom center out
# set key horizontal

set xtics auto
set xrange [0:]
set xlabel "Flow Time (minutes, interval)"
set ylabel "Number of products"

bin_number(x) = floor(x/bin_width)
rounded(x) = bin_width * ( bin_number(x) + 0.5 )

plot 'output_double-capacity_priority.csv' \
    using (rounded($2)):(1) title '0' smooth frequency with boxes, \
 '' using (rounded($3)):(1) title '3' smooth frequency with boxes, \
 '' using (rounded($4)):(1) title '6' smooth frequency with boxes



# plot 3. x-axis: flow time interval, y-axis: number of products

bin_width = 5;  # 5 minutes

set out 'plot_freq_double-speed_priority.svg'
set title "Frequency of flow times (config=double-speed, strategy=priority)"
set boxwidth (bin_width) absolute
set style fill solid 1.0 noborder

set key title "Max Wait (min)"
set key bottom center out
# set key horizontal

set xtics auto
set xrange [0:]
set xlabel "Flow Time (minutes, interval)"
set ylabel "Number of products"

bin_number(x) = floor(x/bin_width)
rounded(x) = bin_width * ( bin_number(x) + 0.5 )

plot 'output_double-speed_priority.csv' \
    using (rounded($2)):(1) title '0' smooth frequency with boxes, \
 '' using (rounded($3)):(1) title '3' smooth frequency with boxes, \
 '' using (rounded($4)):(1) title '6' smooth frequency with boxes