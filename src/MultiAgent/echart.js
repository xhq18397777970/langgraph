	// 假设这是从API获取的数据
	const apiData ={}
    function renderChart(apiData) {
	    const { title, x_data, legend_data, series_data, unit_char,unit } = apiData.data;
	    // 转换数据格式为ECharts需要的格式
	    const chartData = x_data.map((time, index) => {
	        const item = { time };
	        series_data.forEach(series => {
	            item[series.name] = series.value[index];
	        });
	        return item;
	    });
	    // 创建series配置
	    const series = legend_data.map(name => ({
	        name: name,
	        type: 'line',
	        showSymbol: false,
	        lineStyle: {    // <-- 添加这个属性控制线条宽度
          width: 5     // <-- 设置线条宽度，默认是2，3会明显变粗
      },
	        endLabel: {
	            show: true,
	            formatter: function(params) {
	               // return params.seriesName + ': ' + params.value;
	               return params.seriesName 
	            }
	        },
	        labelLayout: {
	            moveOverlap: 'shiftY'
	        },
	        emphasis: {
	            focus: 'series'
	        },
	        encode: {
	            x: 'time',
	            y: name,
	            tooltip: name
	        }
	    }));
	    option = {
	        animationDuration: 1000,
          title: {
              text: title,
              top: 10,                // <-- 向上移动标题，距离顶部10像素
              left: 'center',         // (可选) 保持水平居中
              textStyle: {
                  fontSize: 22,        // (可选) 可以设置一个默认的字体大小
                  fontWeight: 'bold'   // <-- 字体加粗
              }
          },
	        tooltip: {
	            order: 'valueDesc',
	            trigger: 'axis',
              confine: true, // 将 tooltip 限制在图表区域内
              backgroundColor: 'rgba(50, 50, 50, 0.9)',
              borderColor: 'rgba(50, 50, 50, 0.9)',
              textStyle: {
                  color: '#fff'
              },
              axisPointer: {
                  type: 'cross', // 十字准星指示器
                  crossStyle: {
                      color: '#999'
                  },
                  label: {
                      backgroundColor: '#283b56'
                  }
              },
             extraCssText: 'min-width: 180px; box-shadow: 0 0 10px rgba(0, 0, 0, 0.3);', // 设置最小宽度，并添加阴影增强立体感
              padding: [10, 12], // 增加上下和左右的内边距，使内容不拥挤
	            formatter: function(params) {
	                let result = params[0].axisValue.substring(11, 19) + '<br/>';
	                params.forEach(param => {
	                    result += param.marker + param.seriesName + ':                      ' + param.value[param.seriesName] + '<br/>';
	                });
	                return result;
	            }
	        },
          legend: {
              data: legend_data,
              top: 40, // 放在标题下方
              icon: 'roundRect', // 图例图标样式
              itemGap: 25,  // <-- 将图例项之间的间隔设置为25像素（默认是10）
              textStyle: {
                  fontSize: 12,
                  fontWeight: 'bold' // <-- 添加这一行来使字体加粗
              }
          },
        // 4.6 X轴
        xAxis: {
            type: 'category',
            name: '时间',
            nameLocation: 'middle',
            nameGap: 30,
            boundaryGap: false, // 不留白，线条从边缘开始
            axisLine: {
                lineStyle: {
                    color: '#A9A9A9'
                }
            },
            axisTick: {
                show: false
            },
            //年月日时分秒转化为 -> 时分秒
            axisLabel: {
                color: '#666',
                fontWeight: 'bold', // <-- Y轴标签加粗
                // 优化时间显示
                formatter: function(value) {
                    return value.substring(11, 19); // '16:00:00'
                }
            },
            splitLine: {
                show: true,
                lineStyle: {
                    color: '#f0f0f0',
                    type: 'dashed'
                }
            }
        },
	        yAxis: {
	            name: `单位 (${unit})`,
	           // name: '单位',
	            nameGap: 50,
	            nameLocation: 'middle',
	            type: 'value',
	            axisLine: {
                show: true,
                lineStyle: {
                    color: '#A9A9A9'
                }
            },
	            
	        },
	        grid: {
	            right: 140
	        },
	        dataset: {
	            source: chartData
	        },
	        series: series
	    };
	    myChart.setOption(option);
	}
	// 假设myChart已经初始化
	renderChart(apiData);