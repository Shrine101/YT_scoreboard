/**
 * Dart Visualization for Glow-E McThrowy
 * This script creates a visualization layer that shows where darts landed on the dartboard.
 * It automatically clears darts when the player changes.
 */

// Dart Visualization Module
const DartVisualization = (function() {
    // Private variables
    let canvas = null;
    let ctx = null;
    let dartboardImage = null;
    let dartHistory = [];
    let lastFrameRequest = null;
    const maxDartsPerPlayer = 3;
    const dartsColors = ['#ff0000', '#0000ff', '#00ff00', '#ffff00', '#ff00ff', '#00ffff', '#ff8800', '#8800ff'];
    
    // Initialize visualization without modifying layout
    function init() {
      // Find dartboard image without assumptions about container structure
      dartboardImage = document.querySelector('.dartboard-container img');
      if (!dartboardImage) {
        console.warn('Dart visualization: Could not find dartboard image');
        return false;
      }
  
      // Only create canvas if it doesn't exist
      if (!document.getElementById('dart-canvas')) {
        canvas = document.createElement('canvas');
        canvas.id = 'dart-canvas';
        
        // Position it precisely over the dartboard image
        const imgRect = dartboardImage.getBoundingClientRect();
        
        // Copy calculated styles without modifying container
        canvas.style.position = 'absolute';
        canvas.style.pointerEvents = 'none';
        canvas.style.zIndex = '5';
        
        // Insert after the image to ensure proper stacking
        dartboardImage.insertAdjacentElement('afterend', canvas);
        
        // Initial sizing
        resizeCanvas();
      } else {
        canvas = document.getElementById('dart-canvas');
      }
      
      ctx = canvas.getContext('2d');
      
      // Set up resize observer instead of event listener
      const resizeObserver = new ResizeObserver(debounce(() => {
        if (!lastFrameRequest) {
          lastFrameRequest = requestAnimationFrame(resizeCanvas);
        }
      }, 100));
      
      resizeObserver.observe(dartboardImage);
      
      return !!ctx;
    }
    
    // Carefully resize canvas based on actual dartboard image dimensions
    function resizeCanvas() {
      if (!canvas || !dartboardImage) return;
      
      const imgRect = dartboardImage.getBoundingClientRect();
      
      // Set size and position to match image exactly
      canvas.width = imgRect.width;
      canvas.height = imgRect.height;
      canvas.style.left = `${imgRect.left + window.scrollX}px`;
      canvas.style.top = `${imgRect.top + window.scrollY}px`;
      canvas.style.width = `${imgRect.width}px`;
      canvas.style.height = `${imgRect.height}px`;
      
      // Redraw darts after resize
      redrawAllDarts();
      lastFrameRequest = null;
    }
    
    // Convert polar coordinates to canvas coordinates
    function polarToCartesian(r, theta) {
      const standardDartboardRadius = 225;
      const canvasRadius = Math.min(canvas.width, canvas.height) / 2;
      
      const scale = canvasRadius / standardDartboardRadius;
      const radians = (theta - 90) * (Math.PI / 180);
      
      const x = canvas.width / 2 + r * scale * Math.cos(radians);
      const y = canvas.height / 2 + r * scale * Math.sin(radians);
      
      return { x, y };
    }
    
    // Add a new dart to the visualization
    function addDart(playerId, score, multiplier, position_x, position_y) {
      // Ensure we have position data
      if (typeof position_x !== 'number' || typeof position_y !== 'number') {
        console.warn(`Missing position data for dart: Player ${playerId}, Score ${score}×${multiplier}`);
        return null;
      }
      
      const dart = {
        playerId,
        r: position_x,
        theta: position_y,
        score,
        multiplier,
        timestamp: Date.now()
      };
      
      dartHistory.push(dart);
      pruneHistory();
      drawDart(dart);
      
      return dart;
    }
    
    // Draw a single dart
    function drawDart(dart) {
      if (!ctx) return;
      
      const { x, y } = polarToCartesian(dart.r, dart.theta);
      const colorIndex = (dart.playerId - 1) % dartsColors.length;
      const color = dartsColors[colorIndex];
      const opacity = calculateOpacity(dart);
      const hexOpacity = Math.floor(opacity * 255).toString(16).padStart(2, '0');
      
      ctx.beginPath();
      ctx.arc(x, y, 5, 0, Math.PI * 2);
      ctx.fillStyle = `${color}${hexOpacity}`;
      ctx.fill();
      
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 1.5;
      ctx.stroke();
      
      const playerDarts = dartHistory.filter(d => d.playerId === dart.playerId);
      playerDarts.sort((a, b) => b.timestamp - a.timestamp);
      
      if (playerDarts[0] && playerDarts[0].timestamp === dart.timestamp) {
        ctx.fillStyle = '#ffffff';
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        
        const scoreText = dart.multiplier > 1 ? `${dart.score}×${dart.multiplier}` : `${dart.score}`;
        ctx.fillText(scoreText, x, y - 10);
      }
    }
    
    // Calculate opacity based on dart recency
    function calculateOpacity(dart) {
      const playerDarts = dartHistory.filter(d => d.playerId === dart.playerId);
      
      if (playerDarts.length === 1) return 0.9;
      
      playerDarts.sort((a, b) => b.timestamp - a.timestamp);
      const index = playerDarts.findIndex(d => d.timestamp === dart.timestamp);
      
      const baseOpacity = 0.5;
      const step = (0.9 - baseOpacity) / (playerDarts.length - 1);
      
      return baseOpacity + step * (playerDarts.length - 1 - index);
    }
    
    // Redraw all darts
    function redrawAllDarts() {
      if (!ctx) return;
      
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      dartHistory.forEach(drawDart);
    }
    
    // Limit history size
    function pruneHistory() {
      const playerIds = [...new Set(dartHistory.map(d => d.playerId))];
      let newHistory = [];
      
      playerIds.forEach(playerId => {
        const playerDarts = dartHistory.filter(d => d.playerId === playerId);
        
        if (playerDarts.length > maxDartsPerPlayer) {
          playerDarts.sort((a, b) => b.timestamp - a.timestamp);
          newHistory = newHistory.concat(playerDarts.slice(0, maxDartsPerPlayer));
        } else {
          newHistory = newHistory.concat(playerDarts);
        }
      });
      
      dartHistory = newHistory;
    }
    
    // Clear all darts
    function clearCanvas() {
      if (!ctx) return;
      
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      dartHistory = [];
    }
    
    // Utility function for debouncing
    function debounce(func, wait) {
      let timeout;
      return function() {
        const context = this;
        const args = arguments;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), wait);
      };
    }
    
    // Public API
    return {
      initialize: init,
      addDart: addDart,
      clearDarts: clearCanvas,
      redrawDarts: redrawAllDarts
    };
  })();
  
  // Integration script
  document.addEventListener('DOMContentLoaded', function() {
    // Initialize visualization after a slight delay to ensure layout is ready
    setTimeout(() => {
      const initialized = DartVisualization.initialize();
      if (initialized) {
        console.log('Dart visualization initialized successfully');
      }
    }, 500);
    
    // Track player changes
    let currentDartPlayer = null;
    let lastVisualizedThrow = null;
    
    // Store original functions
    const originalUpdateLastThrow = window.updateLastThrow;
    const originalUpdateGame = window.updateGame;
    
    // Override updateLastThrow to add visualization
    window.updateLastThrow = function(lastThrow, players, game_data) {
      if (originalUpdateLastThrow) {
        originalUpdateLastThrow(lastThrow, players, game_data);
      }
      
      if (!lastThrow || !lastThrow.player_id || !lastThrow.score) return;
      
      const throwKey = `${lastThrow.player_id}-${lastThrow.score}-${lastThrow.multiplier}-${lastThrow.points}`;
      if (lastVisualizedThrow === throwKey) return;
      
      DartVisualization.addDart(
        lastThrow.player_id, 
        lastThrow.score, 
        lastThrow.multiplier, 
        lastThrow.position_x, 
        lastThrow.position_y
      );
      
      lastVisualizedThrow = throwKey;
    };
    
    // Override updateGame to check for player changes
    window.updateGame = function(game_data) {
      if (originalUpdateGame) {
        originalUpdateGame(game_data);
      }
      
      if (!game_data || !game_data.current_player) return;
      
      // Handle player change
      if (currentDartPlayer !== null && currentDartPlayer !== game_data.current_player) {
        DartVisualization.clearDarts();
        lastVisualizedThrow = null;
      }
      
      currentDartPlayer = game_data.current_player;
      
      // Process current throws
      if (game_data.current_throws) {
        for (const throwData of game_data.current_throws) {
          if (!throwData || throwData.score === null) continue;
          
          const throwKey = `${game_data.current_player}-${throwData.score}-${throwData.multiplier}-${throwData.points}`;
          if (lastVisualizedThrow === throwKey) continue;
          
          if (throwData.score && throwData.multiplier) {
            DartVisualization.addDart(
              game_data.current_player, 
              throwData.score, 
              throwData.multiplier,
              throwData.position_x,
              throwData.position_y
            );
            
            lastVisualizedThrow = throwKey;
          }
        }
      }
      
      // Handle third throw animation
      if (game_data.animating && game_data.animation_type === 'third_throw' && 
          game_data.next_player !== undefined && game_data.next_player !== null) {
        setTimeout(() => {
          if (currentDartPlayer !== game_data.next_player) {
            DartVisualization.clearDarts();
          }
        }, 3500);
      }
    };
    
    // Handle window resize events to ensure canvas positioning remains correct
    window.addEventListener('resize', function() {
      // Delay redraw to ensure dartboard is resized first
      setTimeout(function() {
        DartVisualization.redrawDarts();
      }, 300);
    });
    
    // Handle I Missed button
    const missedBtn = document.getElementById('i-missed-btn');
    if (missedBtn) {
      missedBtn.addEventListener('click', function() {
        // Wait for missed throw to be processed
        setTimeout(() => {
          // Reset lastVisualizedThrow to ensure next throw is visualized
          lastVisualizedThrow = null;
        }, 500);
      });
    }
  });