<template>
  <div class="kg-container" ref="container">
    <div class="kg-header">
      <h2>Prompt Knowledge Graph</h2>
      <p class="kg-subtitle">{{ entityCount }} entities &middot; {{ edgeCount }} connections &middot; {{ categoryCount }} categories</p>
    </div>
    <div class="kg-controls">
      <button v-for="cat in categories" :key="cat" class="cat-btn" :class="{ active: activeCat === cat }"
        @click="toggleCategory(cat)" :style="{ borderColor: catColors[cat], color: activeCat === cat ? catColors[cat] : '#888' }">
        {{ cat }}
      </button>
      <button class="cat-btn reset" @click="activeCat = null">All</button>
    </div>
    <div class="kg-canvas" ref="canvas"></div>
    <transition name="slide">
      <div class="kg-detail" v-if="selectedNode">
        <button class="close-btn" @click="selectedNode = null">&times;</button>
        <h3 :style="{ color: catColors[selectedNode.category] }">{{ selectedNode.name }}</h3>
        <span class="tag">{{ selectedNode.category }}</span>
        <div class="stat-row">
          <span class="stat-label">出现次数</span>
          <span class="stat-value">{{ selectedNode.count }}</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">关联实体</span>
          <span class="stat-value">{{ selectedNode._neighbors }}</span>
        </div>
        <div class="neighbors">
          <h4>Top Connections</h4>
          <div class="neighbor-item" v-for="n in selectedNode._topNeighbors" :key="n.entity"
            @click="selectByEntity(n.entity)">
            <span class="neighbor-name">{{ n.name }}</span>
            <div class="neighbor-bar-bg">
              <div class="neighbor-bar" :style="{ width: n._pct + '%', background: catColors[n.category] }"></div>
            </div>
            <span class="neighbor-count">{{ n.co_count }}</span>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script>
import * as d3 from 'd3';

export default {
  name: 'KGView',
  data() {
    return {
      graphData: null,
      selectedNode: null,
      activeCat: null,
      categories: [],
      catColors: {},
      entityCount: 0,
      edgeCount: 0,
      categoryCount: 0,
      simulation: null,
      svg: null,
    };
  },
  async mounted() {
    const resp = await fetch('/api/kg/data');
    this.graphData = await resp.json();
    this.categories = this.graphData.categories;
    this.entityCount = this.graphData.entities.length;
    this.edgeCount = this.graphData.edges.length;
    this.categoryCount = this.categories.length;

    const palette = ['#6C5CE7', '#00B894', '#FD79A8', '#FDCB6E', '#00CEC9', '#E17055', '#74B9FF', '#FF6B6B', '#54A0FF'];
    this.catColors = {};
    this.categories.forEach((c, i) => { this.catColors[c] = palette[i % palette.length]; });

    this.renderGraph();
    window.addEventListener('resize', this.onResize);
  },
  beforeUnmount() {
    window.removeEventListener('resize', this.onResize);
    if (this.simulation) this.simulation.stop();
  },
  methods: {
    toggleCategory(cat) {
      this.activeCat = this.activeCat === cat ? null : cat;
      this.updateVisibility();
    },
    updateVisibility() {
      if (!this.svg) return;
      const cat = this.activeCat;
      this.svg.selectAll('.node').each(function(d) {
        const show = !cat || d.category === cat;
        d3.select(this).attr('opacity', show ? 1 : 0.05).attr('pointer-events', show ? 'all' : 'none');
      });
      this.svg.selectAll('.edge').each(function(d) {
        const show = !cat || d.source.category === cat || d.target.category === cat;
        d3.select(this).attr('opacity', show ? 0.3 : 0.01);
      });
    },
    selectByEntity(entityId) {
      const node = this.svg.selectAll('.node').filter(d => d.id === entityId);
      if (node.datum()) this.selectNode(null, node.datum());
    },
    selectNode(event, d) {
      this.selectedNode = d;
      // highlight connected
      this.svg.selectAll('.node').attr('opacity', n => {
        if (n.id === d.id) return 1;
        if (d._neighborSet && d._neighborSet.has(n.id)) return 0.9;
        return 0.1;
      }).attr('stroke-width', n => n.id === d.id ? 3 : 0);
      this.svg.selectAll('.edge').attr('opacity', e => {
        if (e.source.id === d.id || e.target.id === d.id) return 0.7;
        return 0.02;
      });
    },
    resetSelection() {
      this.selectedNode = null;
      this.svg.selectAll('.node').attr('opacity', 1).attr('stroke-width', 0);
      this.svg.selectAll('.edge').attr('opacity', 0.3);
    },
    onResize() {
      if (this.simulation) {
        const w = this.$refs.canvas.clientWidth;
        const h = this.$refs.canvas.clientHeight;
        this.simulation.force('center', d3.forceCenter(w / 2, h / 2));
        this.simulation.alpha(0.3).restart();
      }
    },
    renderGraph() {
      const container = this.$refs.canvas;
      const width = container.clientWidth;
      const height = container.clientHeight || 600;
      const data = this.graphData;

      // Build neighbor sets for quick lookup
      data.entities.forEach(e => {
        e._neighborSet = new Set();
        e._neighbors = 0;
        e._topNeighbors = [];
      });

      // Pre-compute neighbor data
      const neighborMap = {};
      data.edges.forEach(e => {
        if (!neighborMap[e.source]) neighborMap[e.source] = [];
        if (!neighborMap[e.target]) neighborMap[e.target] = [];
        neighborMap[e.source].push({ entity: e.target, co_count: e.weight, ...data.entities.find(x => x.id === e.target) });
        neighborMap[e.target].push({ entity: e.source, co_count: e.weight, ...data.entities.find(x => x.id === e.source) });
      });

      data.entities.forEach(e => {
        const neighbors = neighborMap[e.id] || [];
        e._neighbors = neighbors.length;
        e._neighborSet = new Set(neighbors.map(n => n.entity));
        e._topNeighbors = neighbors
          .sort((a, b) => b.co_count - a.co_count)
          .slice(0, 8)
          .map(n => ({ ...n, _pct: Math.round(n.co_count / e.count * 100) }));
      });

      const svg = d3.select(container).append('svg')
        .attr('width', width)
        .attr('height', height);

      // Zoom & pan
      const g = svg.append('g');
      const zoom = d3.zoom()
        .scaleExtent([0.2, 5])
        .on('zoom', (event) => { g.attr('transform', event.transform); });
      svg.call(zoom);

      this.svg = g;

      // Defs for glow (must be on svg, not g)
      const defs = svg.append('defs');
      const filter = defs.append('filter').attr('id', 'glow');
      filter.append('feGaussianBlur').attr('stdDeviation', '3').attr('result', 'coloredBlur');
      const merge = filter.append('feMerge');
      merge.append('feMergeNode').attr('in', 'coloredBlur');
      merge.append('feMergeNode').attr('in', 'SourceGraphic');

      // Links (inside g for zoom)
      const link = g.append('g').selectAll('line')
        .data(data.edges)
        .join('line')
        .attr('class', 'edge')
        .attr('stroke', d => d._template ? '#FF6B6B' : '#333')
        .attr('stroke-opacity', d => d._template ? 0.4 : 0.3)
        .attr('stroke-width', d => Math.max(0.5, Math.min(3, d.weight / 5)))
        .attr('stroke-dasharray', d => d._template ? '4,3' : null);

      // Nodes (inside g for zoom)
      const node = g.append('g').selectAll('g')
        .data(data.entities)
        .join('g')
        .attr('class', 'node')
        .style('cursor', 'pointer')
        .call(d3.drag()
          .on('start', (event, d) => {
            if (!event.active) this.simulation.alpha(0.3).restart();
            d.fx = d.x; d.fy = d.y;
          })
          .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
          .on('end', (event, d) => {
            d.fx = null; d.fy = null;
            this.simulation.alpha(0).stop();
          })
        );

      // Node shapes: template=hexagon, scene=diamond, entity=circle
      const catColors = this.catColors;
      node.each(function(d) {
        const el = d3.select(this);
        const size = Math.max(5, Math.sqrt(d.count) * 2.5);

        if (d._template) {
          const r = size + 4;
          const pts = Array.from({length: 6}, (_, i) => {
            const a = Math.PI / 3 * i - Math.PI / 6;
            return `${r * Math.cos(a)},${r * Math.sin(a)}`;
          }).join(' ');
          el.append('polygon')
            .attr('points', pts)
            .attr('fill', '#FF6B6B').attr('fill-opacity', 0.9)
            .attr('stroke', '#FF6B6B').attr('stroke-width', 2).attr('stroke-opacity', 0.4);
        } else if (d._scene) {
          const r = size + 2;
          el.append('polygon')
            .attr('points', `0,${-r} ${r},0 0,${r} ${-r},0`)
            .attr('fill', '#54A0FF').attr('fill-opacity', 0.85)
            .attr('stroke', '#54A0FF').attr('stroke-width', 1.5).attr('stroke-opacity', 0.3);
        } else {
          el.append('circle')
            .attr('r', size)
            .attr('fill', catColors[d.category] || '#666')
            .attr('fill-opacity', 0.85)
            .attr('stroke', 'none');
        }
      });

      // Glow on hover
      node.on('mouseenter', function(event, d) { d3.select(this).select('circle,polygon').attr('filter', 'url(#glow)'); })
          .on('mouseleave', function(event, d) { d3.select(this).select('circle,polygon').attr('filter', null); });

      // Labels
      node.append('text')
        .attr('dy', d => -(Math.max(5, Math.sqrt(d.count) * 2.5) + (d._template ? 6 : d._scene ? 4 : 4)))
        .attr('text-anchor', 'middle')
        .attr('fill', d => d._template ? '#FF6B6B' : d._scene ? '#54A0FF' : '#ccc')
        .attr('font-size', d => d._template ? '13px' : d._scene ? '10px' : (d.count > 50 ? '11px' : '9px'))
        .attr('font-weight', d => d._template ? '700' : '400')
        .attr('pointer-events', 'none')
        .text(d => d.name);

      // Click
      node.on('click', this.selectNode.bind(this));

      // Simulation
      this.simulation = d3.forceSimulation(data.entities)
        .force('link', d3.forceLink(data.edges).id(d => d.id).distance(60).strength(0.15))
        .force('charge', d3.forceManyBody().strength(-120).distanceMax(250))
        .force('center', d3.forceCenter(width / 2, height / 2).strength(0.05))
        .force('collision', d3.forceCollide().radius(d => Math.max(8, Math.sqrt(d.count) * 2.5) + 10).strength(1))
        .alphaDecay(0.15)
        .velocityDecay(0.8)
        .on('tick', () => {
          link
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);
          node.attr('transform', d => `translate(${d.x},${d.y})`);
        });

      // Fade in animation
      node.attr('opacity', 0).transition().duration(800).delay((d, i) => i * 15).attr('opacity', 1);
      link.attr('opacity', 0).transition().duration(600).delay(300).attr('opacity', 0.3);

      // Click background to reset
      svg.on('click', (event) => {
        if (event.target.tagName === 'svg' || event.target.tagName === 'rect') this.resetSelection();
      });
    }
  }
};
</script>

<style scoped>
.kg-container {
  height: calc(100vh - 40px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #0a0a0a;
}

.kg-header {
  padding: 16px 24px 8px;
  flex-shrink: 0;
}

.kg-header h2 {
  font-size: 18px;
  font-weight: 600;
  color: #fff;
}

.kg-subtitle {
  font-size: 12px;
  color: #666;
  margin-top: 2px;
}

.kg-controls {
  display: flex;
  gap: 6px;
  padding: 8px 24px 12px;
  flex-wrap: wrap;
  flex-shrink: 0;
}

.cat-btn {
  background: transparent;
  border: 1px solid #333;
  color: #888;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.cat-btn:hover {
  background: #1a1a1a;
}

.cat-btn.active {
  background: #1a1a1a;
  border-width: 2px;
  font-weight: 600;
}

.cat-btn.reset {
  border-color: #444;
  color: #aaa;
}

.kg-canvas {
  flex: 1;
  overflow: hidden;
}

.kg-canvas svg {
  display: block;
}

/* Detail panel */
.kg-detail {
  position: fixed;
  right: 20px;
  top: 80px;
  width: 280px;
  background: #141414;
  border: 1px solid #2a2a2a;
  border-radius: 12px;
  padding: 20px;
  z-index: 100;
  box-shadow: 0 8px 32px rgba(0,0,0,0.5);
}

.close-btn {
  position: absolute;
  top: 8px;
  right: 12px;
  background: none;
  border: none;
  color: #666;
  font-size: 20px;
  cursor: pointer;
}

.close-btn:hover { color: #fff; }

.kg-detail h3 {
  font-size: 16px;
  margin-bottom: 6px;
}

.tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 8px;
  font-size: 11px;
  background: #1a1a1a;
  color: #888;
  margin-bottom: 12px;
}

.stat-row {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px solid #1f1f1f;
}

.stat-label { color: #666; font-size: 12px; }
.stat-value { color: #ccc; font-size: 12px; font-weight: 600; }

.neighbors { margin-top: 12px; }
.neighbors h4 { font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }

.neighbor-item {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  cursor: pointer;
  padding: 2px 0;
}

.neighbor-item:hover .neighbor-name { color: #fff; }

.neighbor-name {
  width: 70px;
  font-size: 11px;
  color: #999;
  flex-shrink: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.neighbor-bar-bg {
  flex: 1;
  height: 4px;
  background: #1f1f1f;
  border-radius: 2px;
  overflow: hidden;
}

.neighbor-bar {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s ease;
}

.neighbor-count {
  font-size: 10px;
  color: #555;
  width: 24px;
  text-align: right;
  flex-shrink: 0;
}

/* Transitions */
.slide-enter-active, .slide-leave-active {
  transition: transform 0.3s ease, opacity 0.3s ease;
}
.slide-enter-from, .slide-leave-to {
  transform: translateX(20px);
  opacity: 0;
}
</style>
