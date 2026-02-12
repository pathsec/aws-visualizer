// ============ CONSTANTS ============
var TYPE_COLORS = {
  'vpc':'#3b82f6','subnet':'#60a5fa','ec2-instance':'#22d3ee',
  'security-group':'#f59e0b','internet-gateway':'#a3e635','nat-gateway':'#84cc16',
  'elastic-ip':'#06b6d4','ebs-volume':'#8b5cf6','vpc-peering':'#c084fc',
  'load-balancer':'#f472b6','target-group':'#ec4899','rds-instance':'#fb923c',
  'rds-cluster':'#f97316','lambda-function':'#fbbf24','ecs-cluster':'#4ade80',
  'ecs-service':'#34d399','eks-cluster':'#2dd4bf','s3-bucket':'#e879f9',
  'iam-user':'#f87171','iam-role':'#fca5a5','iam-policy':'#fecaca',
  'route53-zone':'#a78bfa','route53-record':'#c4b5fd','cloudfront':'#67e8f9',
  'dynamodb-table':'#fdba74','sqs-queue':'#fcd34d','sns-topic':'#86efac',
  'secret':'#fda4af','kms-key':'#d8b4fe','api-gateway':'#f0abfc',
  'acm-cert':'#a5f3fc','cloudtrail':'#bef264','cfn-stack':'#d9f99d',
  'elasticache-cluster':'#fdba74','efs':'#6ee7b7','error':'#ef4444',
};

var EDGE_TYPE_COLORS = {
  'network':'#3b82f6','security':'#f59e0b','security-flow':'#ef4444',
  'compute':'#34d399','storage':'#8b5cf6','dns':'#a78bfa','cdn':'#67e8f9',
  'iam':'#f87171','logging':'#bef264','relationship':'#576577',
};

// ============ SVG ICONS (white, 24x24 viewBox) ============
// Each is a minimal white icon on transparent background.
function svgUri(paths){
  return 'data:image/svg+xml;utf8,' + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" ' +
    'stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
    paths + '</svg>'
  );
}
function svgUriFill(paths){
  return 'data:image/svg+xml;utf8,' + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white" ' +
    'stroke="white" stroke-width="0">' +
    paths + '</svg>'
  );
}

var TYPE_ICONS = {
  // VPC — cloud
  'vpc': svgUri('<path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/>'),
  // Subnet — grid/network partition
  'subnet': svgUri('<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>'),
  // EC2 — computer/monitor
  'ec2-instance': svgUri('<rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>'),
  // Security Group — shield
  'security-group': svgUri('<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>'),
  // Internet Gateway — globe
  'internet-gateway': svgUri('<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>'),
  // NAT Gateway — arrow-right through box
  'nat-gateway': svgUri('<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M8 12h8"/><path d="M13 8l4 4-4 4"/>'),
  // Elastic IP — at-sign / pin
  'elastic-ip': svgUri('<circle cx="12" cy="10" r="3"/><path d="M12 21.7C17.3 17 20 13 20 10a8 8 0 1 0-16 0c0 3 2.7 6.9 8 11.7z"/>'),
  // EBS Volume — hard-drive
  'ebs-volume': svgUri('<line x1="22" y1="12" x2="2" y2="12"/><path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/><line x1="6" y1="16" x2="6.01" y2="16"/><line x1="10" y1="16" x2="10.01" y2="16"/>'),
  // VPC Peering — link
  'vpc-peering': svgUri('<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>'),
  // Load Balancer — git-merge / split arrows
  'load-balancer': svgUri('<circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M6 21V9a9 9 0 0 0 9 9"/>'),
  // Target Group — crosshair
  'target-group': svgUri('<circle cx="12" cy="12" r="10"/><line x1="22" y1="12" x2="18" y2="12"/><line x1="6" y1="12" x2="2" y2="12"/><line x1="12" y1="6" x2="12" y2="2"/><line x1="12" y1="22" x2="12" y2="18"/>'),
  // RDS — database cylinder
  'rds-instance': svgUri('<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>'),
  'rds-cluster': svgUri('<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>'),
  // Lambda — zap / lightning bolt
  'lambda-function': svgUri('<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>'),
  // ECS Cluster — boxes
  'ecs-cluster': svgUri('<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>'),
  // ECS Service — play inside box
  'ecs-service': svgUri('<rect x="2" y="2" width="20" height="20" rx="2"/><polygon points="10 8 16 12 10 16 10 8"/>'),
  // EKS Cluster — ship wheel / kubernetes-like
  'eks-cluster': svgUri('<circle cx="12" cy="12" r="3"/><path d="M12 1v4"/><path d="M12 19v4"/><path d="M1 12h4"/><path d="M19 12h4"/><path d="M4.22 4.22l2.83 2.83"/><path d="M16.95 16.95l2.83 2.83"/><path d="M4.22 19.78l2.83-2.83"/><path d="M16.95 7.05l2.83-2.83"/>'),
  // S3 Bucket — bucket / archive
  's3-bucket': svgUri('<path d="M4 7l1.7 11.07A2 2 0 0 0 7.68 20h8.64a2 2 0 0 0 1.98-1.93L20 7"/><path d="M2 7h20"/><path d="M9 7V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v3"/>'),
  // IAM User — person silhouette
  'iam-user': svgUri('<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>'),
  // IAM Role — user with badge
  'iam-role': svgUri('<path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/><line x1="20" y1="8" x2="20" y2="14"/><line x1="23" y1="11" x2="17" y2="11"/>'),
  // IAM Policy — file-text
  'iam-policy': svgUri('<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>'),
  // Route53 Zone — map
  'route53-zone': svgUri('<polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/>'),
  // Route53 Record — type/text
  'route53-record': svgUri('<polyline points="4 7 4 4 20 4 20 7"/><line x1="9" y1="20" x2="15" y2="20"/><line x1="12" y1="4" x2="12" y2="20"/>'),
  // CloudFront — send / broadcast
  'cloudfront': svgUri('<path d="M22 2L11 13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>'),
  // DynamoDB — table / layers
  'dynamodb-table': svgUri('<path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>'),
  // SQS Queue — list/queue
  'sqs-queue': svgUri('<line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>'),
  // SNS Topic — bell
  'sns-topic': svgUri('<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>'),
  // Secret — lock
  'secret': svgUri('<rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>'),
  // KMS Key — key
  'kms-key': svgUri('<path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.78 7.78 5.5 5.5 0 0 1 7.78-7.78zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/>'),
  // API Gateway — radio tower / broadcast
  'api-gateway': svgUri('<path d="M4.9 19.1C1 15.2 1 8.8 4.9 4.9"/><path d="M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.4"/><circle cx="12" cy="12" r="2"/><path d="M16.2 7.8c2.3 2.3 2.3 6.1 0 8.4"/><path d="M19.1 4.9C23 8.8 23 15.1 19.1 19"/>'),
  // ACM Cert — award/badge
  'acm-cert': svgUri('<circle cx="12" cy="8" r="7"/><polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88"/>'),
  // CloudTrail — eye / audit
  'cloudtrail': svgUri('<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>'),
  // CloudFormation Stack — layers
  'cfn-stack': svgUri('<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>'),
  // ElastiCache — cpu / cache
  'elasticache-cluster': svgUri('<rect x="4" y="4" width="16" height="16" rx="2" ry="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/>'),
  // EFS — folder
  'efs': svgUri('<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>'),
  // Error — alert triangle
  'error': svgUri('<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>'),
};

// Fallback shapes for nodes without icons (shouldn't happen, but just in case)
var TYPE_SHAPES = {
  'vpc':'roundrectangle','subnet':'roundrectangle','ec2-instance':'ellipse',
  'security-group':'diamond','rds-instance':'barrel','rds-cluster':'barrel',
  'lambda-function':'triangle','load-balancer':'hexagon','ecs-cluster':'pentagon',
  'ecs-service':'pentagon','eks-cluster':'pentagon','s3-bucket':'round-rectangle',
  'iam-user':'star','iam-role':'star','cloudfront':'octagon','error':'vee',
};

function typeColor(t){ return TYPE_COLORS[t]||'#576577'; }
function typeIcon(t){ return TYPE_ICONS[t]||null; }
function typeShape(t){ return TYPE_ICONS[t] ? 'ellipse' : (TYPE_SHAPES[t]||'ellipse'); }

function getNodeSize(type){
  var big = ['vpc'];
  var med = ['subnet','ecs-cluster','eks-cluster','load-balancer','rds-instance','rds-cluster'];
  if(big.indexOf(type)!==-1) return 50;
  if(med.indexOf(type)!==-1) return 38;
  return 30;
}

// ============ STATE ============
var cy = null;
var allData = {nodes:[],edges:[]};
var filters = {regions:[],services:[],types:[]};
var activeRegions = new Set();
var activeServices = new Set();
var currentLayout = 'cose';
var stats = {};

// ============ HELPERS ============
function setLoadingText(msg){
  var el = document.getElementById('loading-text');
  if(el) el.textContent = msg;
  console.log('[aws-viz] ' + msg);
}

function showError(msg){
  var overlay = document.getElementById('loading');
  if(overlay){
    overlay.innerHTML = '<div style="color:#f87171;font-family:monospace;font-size:14px;max-width:600px;padding:20px;text-align:left;white-space:pre-wrap;">ERROR: '+msg+'</div>';
  }
}

// ============ INIT ============
async function init(){
  try {
    if(typeof cytoscape === 'undefined'){
      showError('Cytoscape.js failed to load from CDN.\n\nCheck your network or place cytoscape.min.js in static/ and update index.html.');
      return;
    }
    setLoadingText('Cytoscape.js loaded OK');

    setLoadingText('Fetching filters...');
    var fResp = await fetch('/api/filters');
    if(!fResp.ok) throw new Error('GET /api/filters failed: ' + fResp.status);
    filters = await fResp.json();
    setLoadingText('Filters: ' + filters.regions.length + ' regions, ' + filters.services.length + ' services');

    setLoadingText('Fetching stats...');
    var sResp = await fetch('/api/stats');
    if(!sResp.ok) throw new Error('GET /api/stats failed: ' + sResp.status);
    stats = await sResp.json();

    renderStats();
    activeRegions = new Set(filters.regions);
    activeServices = new Set(filters.services);
    renderChips();
    renderLegend();
    await renderSources();

    setLoadingText('Fetching graph data...');
    await loadGraph();

    setLoadingText('Done!');
    document.getElementById('loading').classList.add('hidden');
    console.log('[aws-viz] Initialization complete');

  } catch(err) {
    console.error('[aws-viz] Init failed:', err);
    showError('Initialization failed:\n\n' + err.message + '\n\nCheck browser console (F12) and Flask terminal.');
  }
}

// ============ GRAPH LOADING ============
async function loadGraph(){
  var params = new URLSearchParams();

  // If no regions or services are active, send _none_ to get a blank canvas
  if(activeRegions.size === 0){
    params.set('regions','_none_');
  } else if(activeRegions.size < filters.regions.length){
    params.set('regions',[...activeRegions].join(','));
  }
  if(activeServices.size === 0){
    params.set('services','_none_');
  } else if(activeServices.size < filters.services.length){
    params.set('services',[...activeServices].join(','));
  }

  var url = '/api/graph?' + params.toString();
  console.log('[aws-viz] Fetching: ' + url);
  var resp = await fetch(url);
  if(!resp.ok) throw new Error('GET ' + url + ' failed: ' + resp.status);
  allData = await resp.json();
  console.log('[aws-viz] Got ' + allData.nodes.length + ' nodes, ' + allData.edges.length + ' edges');

  buildCytoscape(allData);
  updateCounts();
}

function buildCytoscape(data){
  var elements = [];
  data.nodes.forEach(function(n){
    elements.push({group:'nodes',data:{
      id:n.id, label:n.label, type:n.type, region:n.region,
      service:n.service, metadata:n.metadata,
      color:typeColor(n.type),
      shape:typeShape(n.type),
      size:getNodeSize(n.type),
      icon: typeIcon(n.type) || '',
    }});
  });
  data.edges.forEach(function(e,i){
    elements.push({group:'edges',data:{
      id:'e'+i, source:e.source, target:e.target,
      label:e.label, type:e.type,
      color:EDGE_TYPE_COLORS[e.type]||'#576577',
    }});
  });

  console.log('[aws-viz] Building cytoscape with ' + elements.length + ' elements');

  if(cy){ cy.destroy(); cy = null; }

  cy = cytoscape({
    container: document.getElementById('cy'),
    elements: elements,
    minZoom: 0.1,
    maxZoom: 4,
    wheelSensitivity: 0.3,
    pixelRatio: 2,
    textureOnViewport: false,
    style: [
      // ── Default node with icon ──
      {
        selector: 'node',
        style: {
          'background-color': 'data(color)',
          'label': 'data(label)',
          'shape': 'data(shape)',
          'width': 'data(size)',
          'height': 'data(size)',
          // Icon rendering
          'background-image': 'data(icon)',
          'background-fit': 'contain',
          'background-clip': 'none',
          'background-width': '60%',
          'background-height': '60%',
          'background-image-opacity': 0.95,
          // Text
          'font-size': '11px',
          'font-family': "'JetBrains Mono', monospace",
          'font-weight': 700,
          'color': '#e8ecf2',
          'text-valign': 'bottom',
          'text-halign': 'center',
          'text-margin-y': 8,
          'text-wrap': 'ellipsis',
          'text-max-width': '100px',
          // Border
          'border-width': 2,
          'border-color': 'data(color)',
          'border-opacity': 0.5,
          'background-opacity': 0.9,
          // Text bg — fully opaque for sharp text
          'text-background-color': '#0a0e17',
          'text-background-opacity': 1,
          'text-background-padding': '3px',
          'text-background-shape': 'roundrectangle',
          'overlay-padding': '4px',
          'z-index': 10,
        }
      },
      // ── Error node override ──
      {
        selector: 'node[type="error"]',
        style: {
          'background-color': '#ef4444',
          'border-color': '#ef4444',
          'font-size': '10px',
          'width': 22, 'height': 22,
        }
      },
      // ── Edges ──
      {
        selector: 'edge',
        style: {
          'width': 1.5,
          'line-color': 'data(color)',
          'target-arrow-color': 'data(color)',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'arrow-scale': 0.7,
          'opacity': 0.5,
          // Label — always present but hidden until zoom threshold
          'label': 'data(label)',
          'font-size': '10px',
          'font-family': "'JetBrains Mono', monospace",
          'font-weight': 700,
          'color': '#c0cede',
          'text-rotation': 'autorotate',
          'text-margin-y': -12,
          'text-background-color': '#0c1219',
          'text-background-opacity': 1,
          'text-background-padding': '4px',
          'text-background-shape': 'roundrectangle',
          'text-opacity': 0,
        }
      },
      // ── Edges visible at zoom — toggled by zoom handler ──
      {
        selector: 'edge.show-label',
        style: {
          'text-opacity': 1,
        }
      },
      // ── Security flow dashed ──
      {
        selector: 'edge[type="security-flow"]',
        style: {
          'line-style': 'dashed',
          'line-dash-pattern': [6,3],
          'width': 2.5,
          'opacity': 0.75,
          'color': '#fca5a5',
        }
      },
      // ── Selected ──
      {
        selector: 'node:selected',
        style: {
          'border-width': 3,
          'border-color': '#22d3ee',
          'background-opacity': 1,
          'z-index': 999,
          'text-background-opacity': 1,
          'font-size': '13px',
        }
      },
      // ── Highlighted ──
      {
        selector: '.highlighted',
        style: {
          'border-width': 3,
          'border-color': '#22d3ee',
          'background-opacity': 1,
          'z-index': 100,
        }
      },
      {
        selector: '.highlighted-edge',
        style: {
          'width': 3,
          'opacity': 0.95,
          'z-index': 100,
          'text-opacity': 1,
          'font-size': '11px',
          'color': '#f0f4f8',
          'text-background-opacity': 1,
        }
      },
      // ── Faded ──
      {
        selector: '.faded',
        style: {
          'opacity': 0.08,
        }
      },
    ],
  });

  // Click node
  cy.on('tap', 'node', function(evt){
    var node = evt.target;
    showDetail(node.data());
    highlightNeighbors(node);
  });
  // Click background
  cy.on('tap', function(evt){
    if(evt.target === cy){ clearHighlight(); hideDetail(); }
  });
  // Hover
  cy.on('mouseover', 'node', function(){ document.getElementById('cy').style.cursor = 'pointer'; });
  cy.on('mouseout', 'node', function(){ document.getElementById('cy').style.cursor = 'default'; });

  // Zoom-based edge label visibility
  var EDGE_LABEL_ZOOM_THRESHOLD = 1.3;
  var edgeLabelsVisible = false;

  function updateEdgeLabels(){
    var zoom = cy.zoom();
    if(zoom >= EDGE_LABEL_ZOOM_THRESHOLD && !edgeLabelsVisible){
      cy.edges().addClass('show-label');
      edgeLabelsVisible = true;
    } else if(zoom < EDGE_LABEL_ZOOM_THRESHOLD && edgeLabelsVisible){
      cy.edges().removeClass('show-label');
      edgeLabelsVisible = false;
    }
  }

  cy.on('zoom', updateEdgeLabels);
  // Also run once on init
  updateEdgeLabels();

  console.log('[aws-viz] Cytoscape created, running layout...');
  runLayout();
}

// ============ LAYOUT ============
function runLayout(){
  if(!cy) return;
  var opts;
  switch(currentLayout){
    case 'cose':
      opts = {
        name:'cose', animate:true, animationDuration:600,
        nodeRepulsion:function(){return 8000;},
        idealEdgeLength:function(){return 100;},
        edgeElasticity:function(){return 100;},
        gravity:0.25, padding:40, randomize:true,
      };
      break;
    case 'breadthfirst':
      opts = {
        name:'breadthfirst', animate:true, animationDuration:500,
        directed:true, padding:40, spacingFactor:1.2,
        roots: cy.nodes().filter(function(n){
          return n.data('type')==='vpc' || (n.indegree()===0 && n.outdegree()>0);
        })
      };
      break;
    case 'grid':
      opts = {
        name:'grid', animate:true, animationDuration:500, padding:40,
        sort: function(a,b){
          var s = a.data('service').localeCompare(b.data('service'));
          return s!==0 ? s : a.data('type').localeCompare(b.data('type'));
        }
      };
      break;
    default:
      opts = {name:'cose',animate:true,animationDuration:600,padding:40};
  }
  cy.layout(opts).run();
}

function setLayout(name, el){
  document.querySelectorAll('.layout-option').forEach(function(e){e.classList.remove('active');});
  el.classList.add('active');
  currentLayout = name;
  runLayout();
}

// ============ HIGHLIGHT ============
function highlightNeighbors(node){
  clearHighlight();
  var neighborhood = node.neighborhood().add(node);
  cy.elements().addClass('faded');
  neighborhood.removeClass('faded');
  node.removeClass('faded');
  neighborhood.nodes().addClass('highlighted');
  neighborhood.edges().addClass('highlighted-edge');
}

function clearHighlight(){
  if(!cy) return;
  cy.elements().removeClass('faded highlighted highlighted-edge');
}

// ============ DETAIL PANEL ============
function showDetail(data){
  document.getElementById('detail-empty').style.display = 'none';
  var content = document.getElementById('detail-content');
  content.style.display = 'block';

  var color = typeColor(data.type);
  var meta = data.metadata || {};

  var propsHtml = '';
  var allProps = Object.assign({id: data.id, region: data.region, service: data.service}, meta);

  for(var key in allProps){
    if(!allProps.hasOwnProperty(key)) continue;
    var val = allProps[key];
    if(val === null || val === undefined || val === '' || key === 'rules') continue;
    var displayVal = val;
    var cls = '';
    if(typeof val === 'boolean'){
      displayVal = val ? '✓ yes' : '✗ no';
      cls = val ? 'status-ok' : 'status-warn';
    } else if(typeof val === 'object'){
      displayVal = JSON.stringify(val).slice(0, 80);
    }
    if(key === 'state' || key === 'status'){
      var v = String(val).toLowerCase();
      if(['running','available','active','enabled','ok','issued'].indexOf(v)!==-1) cls = 'status-ok';
      else if(['stopped','pending','creating'].indexOf(v)!==-1) cls = 'status-warn';
      else if(['terminated','error','failed','deleted'].indexOf(v)!==-1) cls = 'status-err';
    }
    propsHtml += '<div class="detail-prop">' +
      '<span class="detail-prop-key">'+escHtml(key)+'</span>' +
      '<span class="detail-prop-val '+cls+'">'+escHtml(String(displayVal))+'</span></div>';
  }

  var rulesHtml = '';
  if(meta.rules && meta.rules.length > 0){
    rulesHtml = '<div><div class="detail-section-title">Inbound Rules</div><div class="detail-props">';
    for(var i=0;i<meta.rules.length;i++){
      rulesHtml += '<div class="detail-prop"><span class="detail-prop-val" style="text-align:left;font-size:11px;">→ '+escHtml(meta.rules[i])+'</span></div>';
    }
    rulesHtml += '</div></div>';
  }

  var connHtml = '';
  var connEdges = allData.edges.filter(function(e){ return e.source === data.id || e.target === data.id; });
  if(connEdges.length > 0){
    connHtml = '<div><div class="detail-section-title">Connections ('+connEdges.length+')</div><div class="detail-connections">';
    for(var j=0;j<connEdges.length;j++){
      var e = connEdges[j];
      var isSource = e.source === data.id;
      var otherId = isSource ? e.target : e.source;
      var otherNode = allData.nodes.find(function(n){ return n.id === otherId; });
      var otherLabel = otherNode ? otherNode.label : otherId;
      var arrow = isSource ? '→' : '←';
      connHtml += '<div class="connection-item" onclick="navigateToNode(\''+escAttr(otherId)+'\')">' +
        '<span class="connection-arrow">'+arrow+'</span>' +
        '<span class="connection-label">'+escHtml(e.label)+'</span>' +
        '<span class="connection-target">'+escHtml(otherLabel)+'</span></div>';
    }
    connHtml += '</div></div>';
  }

  content.innerHTML =
    '<div class="detail-header">' +
      '<div class="detail-type-badge" style="background:'+color+'22;color:'+color+';border:1px solid '+color+'44;">'+escHtml(data.type)+'</div>' +
      '<div class="detail-label">'+escHtml(data.label)+'</div>' +
      '<div class="detail-region">'+escHtml(data.region)+' · '+escHtml(data.service)+'</div>' +
    '</div>' +
    '<div class="detail-body">' +
      '<div><div class="detail-section-title">Properties</div><div class="detail-props">'+propsHtml+'</div></div>' +
      rulesHtml + connHtml +
    '</div>';
}

function hideDetail(){
  document.getElementById('detail-empty').style.display = 'flex';
  document.getElementById('detail-content').style.display = 'none';
}

function navigateToNode(nodeId){
  if(!cy) return;
  var node = cy.getElementById(nodeId);
  if(node && node.length > 0){
    cy.animate({center:{eles:node},zoom:2},{duration:400});
    setTimeout(function(){
      node.select();
      showDetail(node.data());
      highlightNeighbors(node);
    },450);
  }
}

// ============ SEARCH ============
(function(){
  var searchTimeout;
  document.addEventListener('DOMContentLoaded', function(){
    var searchInput = document.getElementById('search-input');
    if(!searchInput) return;
    searchInput.addEventListener('input', function(){
      clearTimeout(searchTimeout);
      var self = this;
      searchTimeout = setTimeout(function(){
        if(!cy) return;
        var q = self.value.trim().toLowerCase();
        if(!q){ clearHighlight(); return; }
        var matches = cy.nodes().filter(function(n){
          return n.data('label').toLowerCase().indexOf(q)!==-1 ||
                 n.data('id').toLowerCase().indexOf(q)!==-1 ||
                 n.data('type').toLowerCase().indexOf(q)!==-1;
        });
        if(matches.length > 0){
          cy.elements().addClass('faded');
          matches.removeClass('faded').addClass('highlighted');
          matches.neighborhood().edges().removeClass('faded').addClass('highlighted-edge');
          matches.neighborhood().nodes().removeClass('faded');
          if(matches.length <= 5) cy.animate({fit:{eles:matches,padding:80}},{duration:400});
        } else { clearHighlight(); }
      }, 200);
    });
    searchInput.addEventListener('keydown', function(e){
      if(!cy) return;
      if(e.key === 'Enter'){
        var q = this.value.trim().toLowerCase();
        var match = cy.nodes().filter(function(n){ return n.data('label').toLowerCase().indexOf(q)!==-1; });
        if(match.length > 0){
          var first = match[0];
          cy.animate({center:{eles:first},zoom:2},{duration:400});
          setTimeout(function(){ first.select(); showDetail(first.data()); highlightNeighbors(first); },450);
        }
      }
      if(e.key === 'Escape'){ this.value = ''; clearHighlight(); }
    });
  });
})();

// ============ CHIPS / FILTERS ============
function renderChips(){
  var rc = document.getElementById('region-chips');
  rc.innerHTML = '';
  filters.regions.forEach(function(r){
    var chip = document.createElement('div');
    chip.className = 'chip' + (activeRegions.has(r) ? ' active' : '');
    chip.textContent = r;
    chip.dataset.value = r;
    chip.dataset.group = 'region';
    chip.addEventListener('click', function(){ toggleChip(this); });
    rc.appendChild(chip);
  });
  var sc = document.getElementById('service-chips');
  sc.innerHTML = '';
  filters.services.forEach(function(s){
    var chip = document.createElement('div');
    chip.className = 'chip' + (activeServices.has(s) ? ' active' : '');
    chip.textContent = s;
    chip.dataset.value = s;
    chip.dataset.group = 'service';
    chip.addEventListener('click', function(){ toggleChip(this); });
    sc.appendChild(chip);
  });
}

function toggleChip(chip){
  var group = chip.dataset.group;
  var val = chip.dataset.value;
  var set = group === 'region' ? activeRegions : activeServices;
  if(set.has(val)){ set.delete(val); chip.classList.remove('active'); }
  else { set.add(val); chip.classList.add('active'); }
  loadGraph();
}

function selectAllChips(group){
  var set = group === 'region' ? activeRegions : activeServices;
  var list = group === 'region' ? filters.regions : filters.services;
  list.forEach(function(v){ set.add(v); });
  renderChips(); loadGraph();
}

function clearAllChips(group){
  (group === 'region' ? activeRegions : activeServices).clear();
  renderChips(); loadGraph();
}

function resetAll(){
  activeRegions = new Set(filters.regions);
  activeServices = new Set(filters.services);
  document.getElementById('search-input').value = '';
  renderChips(); loadGraph();
}

// ============ LEGEND ============
function renderLegend(){
  var el = document.getElementById('legend');
  var types = Object.keys(TYPE_COLORS);
  el.innerHTML = types.map(function(t){
    var icon = TYPE_ICONS[t];
    var iconHtml = icon
      ? '<img src="'+icon+'" style="width:12px;height:12px;filter:brightness(0.7);" />'
      : '<div class="legend-dot" style="background:'+TYPE_COLORS[t]+'"></div>';
    return '<div class="legend-item">' +
      '<div class="legend-dot" style="background:'+TYPE_COLORS[t]+'"></div>' +
      iconHtml + ' ' + t + '</div>';
  }).join('');
}

// ============ STATS ============
function renderStats(){
  var el = document.getElementById('stats-panel');
  var items = [
    ['Ingested', (stats.ingestion_time||'').split('T')[0] || '—'],
    ['Regions scanned', stats.regions_scanned],
    ['Active regions', stats.regions_active],
    ['EC2 instances', stats.ec2_instances],
    ['VPCs', stats.vpcs],
    ['Lambda funcs', stats.lambda_functions],
    ['RDS instances', stats.rds_instances],
    ['S3 buckets', stats.s3_buckets],
    ['IAM users', stats.iam_users],
    ['IAM roles', stats.iam_roles],
    ['Access errors', stats.total_errors],
  ];
  el.innerHTML = items.map(function(item){
    return '<div class="detail-prop"><span class="detail-prop-key">'+item[0]+'</span><span class="detail-prop-val">'+(item[1]!=null?item[1]:'—')+'</span></div>';
  }).join('');
  var timeEl = document.getElementById('ingestion-time');
  if(timeEl) timeEl.textContent = (stats.ingestion_time||'').split('T')[0] || '';
}

function updateCounts(){
  document.getElementById('stat-nodes').textContent = allData.nodes.length;
  document.getElementById('stat-edges').textContent = allData.edges.length;
  document.getElementById('visible-nodes').textContent = allData.nodes.length;
  document.getElementById('visible-edges').textContent = allData.edges.length;
}

// ============ UTIL ============
function escHtml(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function escAttr(s){ return String(s).replace(/\\/g,'\\\\').replace(/'/g,"\\'").replace(/"/g,'&quot;'); }

// ============ DATA MANAGEMENT ============
async function handleFileUpload(input){
  var files = input.files;
  if(!files || files.length === 0) return;

  var formData = new FormData();
  for(var i = 0; i < files.length; i++){
    formData.append('file', files[i]);
  }

  try {
    var resp = await fetch('/api/upload', {method:'POST', body:formData});
    var result = await resp.json();
    if(!resp.ok){
      alert('Upload error: ' + (result.error || 'unknown'));
      return;
    }
    console.log('[aws-viz] Uploaded:', result.added, '→', result.nodes, 'nodes');
    await refreshAfterDataChange();
  } catch(err){
    alert('Upload failed: ' + err.message);
  }
  // Reset the file input so the same file can be re-uploaded
  input.value = '';
}

async function clearAllData(){
  try {
    await fetch('/api/clear', {method:'POST'});
    console.log('[aws-viz] All data cleared');
    await refreshAfterDataChange();
  } catch(err){
    alert('Clear failed: ' + err.message);
  }
}

async function removeSource(idx){
  try {
    var resp = await fetch('/api/remove_source', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({index: idx})
    });
    var result = await resp.json();
    if(!resp.ok){
      alert('Remove error: ' + (result.error || 'unknown'));
      return;
    }
    console.log('[aws-viz] Removed:', result.removed);
    await refreshAfterDataChange();
  } catch(err){
    alert('Remove failed: ' + err.message);
  }
}

async function refreshAfterDataChange(){
  // Re-fetch everything: filters, stats, sources, graph
  var fResp = await fetch('/api/filters');
  filters = await fResp.json();
  var sResp = await fetch('/api/stats');
  stats = await sResp.json();

  activeRegions = new Set(filters.regions);
  activeServices = new Set(filters.services);
  renderChips();
  renderStats();
  renderLegend();
  await renderSources();
  await loadGraph();
}

async function renderSources(){
  var el = document.getElementById('source-list');
  if(!el) return;
  try {
    var resp = await fetch('/api/sources');
    var sources = await resp.json();
    if(sources.length === 0){
      el.innerHTML = '<div class="source-empty">No data loaded</div>';
      return;
    }
    el.innerHTML = sources.map(function(s, i){
      return '<div class="source-item">' +
        '<span class="source-name" title="'+escHtml(s.name)+'">'+escHtml(s.name)+'</span>' +
        '<button class="source-remove" title="Remove" onclick="removeSource('+i+')">✕</button>' +
        '</div>';
    }).join('');
  } catch(e){
    el.innerHTML = '<div class="source-empty">Error loading sources</div>';
  }
}

// ============ GO ============
console.log('[aws-viz] app.js loaded, calling init()...');
init();
