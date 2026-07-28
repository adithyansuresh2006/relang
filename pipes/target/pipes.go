// pipes.go — Animated pipes terminal screensaver in Go.
// Functionally equivalent to the Python reference implementation.
//
// Build:
//   go mod tidy
//   go build -o pipes .
//
// Run:
//   ./pipes
//
// Flags:
//   -p  number of pipes (default 1)
//   -f  frames per second (20-100, default 75)
//   -s  steadiness — higher = less turning (5-15, default 13)
//   -r  character limit before screen reset (default 2000)
//   -R  random start positions and directions
//   -B  disable bold
//   -C  disable colour
//   -P  pipe style index (0-9)
//   -K  keep pipe style when wrapping edges
//   -v  print version and exit

package main

import (
	"flag"
	"fmt"
	"math/rand"
	"os"
	"time"

	"github.com/gdamore/tcell/v2"
)

// ────────────────────────── types ──────────────────────────

// Direction mirrors the Python IntEnum: UP=0, RIGHT=1, DOWN=2, LEFT=3.
type Direction int

const (
	DirUp    Direction = 0
	DirRight Direction = 1
	DirDown  Direction = 2
	DirLeft  Direction = 3
)

// PipeState holds all mutable state for one pipe.
type PipeState struct {
	x, y      int
	direction Direction
	pipeType  int
	colorIdx  int
	style     tcell.Style
}

// Config holds all user-configurable parameters.
type Config struct {
	numPipes    int
	fps         int
	steady      int
	limit       int
	randomStart bool
	bold        bool
	color       bool
	keepStyle   bool
	colors      []int // ANSI colour indices
	pipeTypes   []int // active pipe style indices
}

// ──────────────────────── pipe-sets ────────────────────────

// pipeSets contains the pipe drawing characters for each of the 10 styles.
// Indexing: index = old_direction*4 + new_direction.
// This mirrors PIPE_SETS from the Python renderer, padded to 16 entries.
var pipeSets = [10][16]rune{
	// 0 — heavy box-drawing
	{'┃', '┏', ' ', '┓', '┛', '━', '┓', ' ', ' ', '┗', '┃', '┛', '┗', ' ', '┏', '━'},
	// 1 — curved
	{'│', '╭', ' ', '╮', '╯', '─', '╮', ' ', ' ', '╰', '│', '╯', '╰', ' ', '╭', '─'},
	// 2 — light
	{'│', '┌', ' ', '┐', '┘', '─', '┐', ' ', ' ', '└', '│', '┘', '└', ' ', '┌', '─'},
	// 3 — double
	{'║', '╔', ' ', '╗', '╝', '═', '╗', ' ', ' ', '╚', '║', '╝', '╚', ' ', '╔', '═'},
	// 4 — ASCII knobby
	{'|', '+', ' ', '+', '+', '-', '+', ' ', ' ', '+', '|', '+', '+', ' ', '+', '-'},
	// 5 — angles / slashes
	{'|', '/', ' ', '\\', ' ', '\\', '-', '\\', ' ', ' ', '\\', '|', '/', '\\', ' ', '/'},
	// 6 — dots
	{'.', 'o', ' ', '.', '.', '.', '.', ' ', ' ', '.', '.', '.', '.', ' ', '.', 'o'},
	// 7 — dots-O
	{'.', 'o', ' ', 'o', 'o', '.', 'o', ' ', ' ', 'o', '.', 'o', 'o', ' ', 'o', '.'},
	// 8 — slashes / bars
	{'-', '\\', ' ', '/', '\\', '|', '/', ' ', ' ', '/', '-', '\\', '/', ' ', '\\', '|'},
	// 9 — mixed heavy+light
	{'╿', '┍', ' ', '┑', '┚', '╼', '┒', ' ', ' ', '┕', '╽', '┙', '┖', ' ', '┎', '╾'},
}

// tcellColors maps Python curses colour indices (0-7) to tcell colours.
// Curses: 0=Black, 1=Red, 2=Green, 3=Yellow, 4=Blue, 5=Magenta, 6=Cyan, 7=White.
var tcellColors = [8]tcell.Color{
	tcell.ColorBlack,
	tcell.ColorMaroon,
	tcell.ColorGreen,
	tcell.ColorOlive,
	tcell.ColorNavy,
	tcell.ColorPurple,
	tcell.ColorTeal,
	tcell.ColorSilver,
}

// ──────────────────────── helpers ──────────────────────────

func clamp(v, lo, hi int) int {
	if v < lo {
		return lo
	}
	if v > hi {
		return hi
	}
	return v
}

func randChoice(arr []int) int {
	return arr[rand.Intn(len(arr))]
}

// makeStyle builds a tcell.Style for a given colour index and the current config.
func makeStyle(cfg *Config, colorIdx int) tcell.Style {
	st := tcell.StyleDefault
	if cfg.color && colorIdx >= 0 && colorIdx < 8 {
		st = st.Foreground(tcellColors[colorIdx])
	}
	if cfg.bold {
		st = st.Bold(true)
	}
	return st
}

// ──────────────────────── pipe logic ────────────────────────

func initPipes(cfg *Config, screen tcell.Screen) []PipeState {
	w, h := screen.Size()
	pipes := make([]PipeState, cfg.numPipes)
	for i := range pipes {
		var dir Direction
		var px, py int
		if cfg.randomStart {
			dir = Direction(rand.Intn(4))
			px = rand.Intn(w)
			py = rand.Intn(h)
		} else {
			dir = DirUp
			px = w / 2
			py = h / 2
		}
		ci := randChoice(cfg.colors)
		pipes[i] = PipeState{
			x:         px,
			y:         py,
			direction: dir,
			pipeType:  randChoice(cfg.pipeTypes),
			colorIdx:  ci,
			style:     makeStyle(cfg, ci),
		}
	}
	return pipes
}

// updatePipes advances every pipe by one step and draws its segment.
// This mirrors _update_pipes() in pipes.py.
func updatePipes(pipes []PipeState, cfg *Config, screen tcell.Screen) {
	w, h := screen.Size()
	for i := range pipes {
		p := &pipes[i]
		x, y := p.x, p.y
		oldDir := int(p.direction)

		// Advance position.
		// Python: if direction % 2: x += -direction + 2   (RIGHT→+1, LEFT→-1)
		//         else:             y += direction - 1      (UP→-1,  DOWN→+1)
		if oldDir%2 != 0 {
			x += -oldDir + 2
		} else {
			y += oldDir - 1
		}

		// Wrap around edges and optionally randomise style.
		if x < 0 || x >= w || y < 0 || y >= h {
			if !cfg.keepStyle {
				p.pipeType = randChoice(cfg.pipeTypes)
				p.colorIdx = randChoice(cfg.colors)
				p.style = makeStyle(cfg, p.colorIdx)
			}
			x = ((x % w) + w) % w
			y = ((y % h) + h) % h
		}

		// Choose new direction (turn with probability ≈ 2/steady).
		newDir := oldDir
		if rand.Intn(cfg.steady) <= 1 {
			turn := 2*rand.Intn(2) - 1 // -1 or +1
			newDir = (oldDir + turn + 4) % 4
		}

		// Draw the appropriate character at the CURRENT (old) position,
		// then commit the new position — same order as the Python reference.
		idx := oldDir*4 + newDir
		ch := pipeSets[p.pipeType][idx]
		screen.SetContent(p.x, p.y, ch, nil, p.style)

		p.x = x
		p.y = y
		p.direction = Direction(newDir)
	}
}

// ──────────────────────── main ──────────────────────────────

func main() {
	// ── defaults (match Python DEFAULT_CONFIG) ──
	cfg := &Config{
		numPipes:  1,
		fps:       75,
		steady:    13,
		limit:     2000,
		bold:      true,
		color:     true,
		colors:    []int{1, 2, 3, 4, 5, 6, 7, 0},
		pipeTypes: []int{0},
	}

	// ── flags (mirror Python argparse) ──
	flag.IntVar(&cfg.numPipes, "p", cfg.numPipes, "number of pipes")
	flag.IntVar(&cfg.fps, "f", cfg.fps, "frames per second (20-100)")
	flag.IntVar(&cfg.steady, "s", cfg.steady, "steadiness (5-15)")
	flag.IntVar(&cfg.limit, "r", cfg.limit, "character limit before reset")
	flag.BoolVar(&cfg.randomStart, "R", false, "random start positions and directions")
	noBold := flag.Bool("B", false, "disable bold")
	noColor := flag.Bool("C", false, "disable colour")
	pipeStyle := flag.Int("P", -1, "pipe style (0-9)")
	flag.BoolVar(&cfg.keepStyle, "K", false, "keep style when pipe wraps")
	showVer := flag.Bool("v", false, "print version and exit")
	flag.Parse()

	if *showVer {
		fmt.Println("pipes-go v1.0")
		os.Exit(0)
	}
	if *noBold {
		cfg.bold = false
	}
	if *noColor {
		cfg.color = false
	}
	if *pipeStyle >= 0 {
		cfg.pipeTypes = []int{clamp(*pipeStyle, 0, 9)}
	}
	cfg.fps = clamp(cfg.fps, 20, 100)
	cfg.steady = clamp(cfg.steady, 5, 15)
	if cfg.limit < 0 {
		cfg.limit = 0
	}

	rand.Seed(time.Now().UnixNano()) //nolint:staticcheck

	// ── terminal setup ──
	screen, err := tcell.NewScreen()
	if err != nil {
		fmt.Fprintf(os.Stderr, "pipes: %v\n", err)
		os.Exit(1)
	}
	if err := screen.Init(); err != nil {
		fmt.Fprintf(os.Stderr, "pipes: %v\n", err)
		os.Exit(1)
	}
	defer screen.Fini()

	screen.SetStyle(tcell.StyleDefault)
	screen.HideCursor()
	screen.Clear()

	pipes := initPipes(cfg, screen)
	count := 0
	w, h := screen.Size()

	// Frame ticker drives the animation.
	ticker := time.NewTicker(time.Duration(1000/cfg.fps) * time.Millisecond)
	defer ticker.Stop()

	// tcell.PollEvent() blocks, so drive it from a goroutine.
	evCh := make(chan tcell.Event, 16)
	go func() {
		for {
			ev := screen.PollEvent()
			if ev == nil {
				return // screen was closed
			}
			evCh <- ev
		}
	}()

	// ── main loop ──
	for {
		select {

		// ── keyboard / resize events ──
		case ev := <-evCh:
			switch e := ev.(type) {

			case *tcell.EventKey:
				key := e.Key()
				r := e.Rune()
				// Normalise to upper-case
				if r >= 'a' && r <= 'z' {
					r -= 32
				}
				switch {
				case key == tcell.KeyEscape || r == '?':
					return
				case r == 'P' && cfg.steady < 15:
					cfg.steady++
				case r == 'O' && cfg.steady > 3:
					cfg.steady--
				case r == 'F' && cfg.fps < 100:
					cfg.fps++
					ticker.Reset(time.Duration(1000/cfg.fps) * time.Millisecond)
				case r == 'D' && cfg.fps > 20:
					cfg.fps--
					ticker.Reset(time.Duration(1000/cfg.fps) * time.Millisecond)
				case r == 'B':
					cfg.bold = !cfg.bold
					for i := range pipes {
						pipes[i].style = makeStyle(cfg, pipes[i].colorIdx)
					}
				case r == 'C':
					cfg.color = !cfg.color
					for i := range pipes {
						pipes[i].style = makeStyle(cfg, pipes[i].colorIdx)
					}
				case r == 'K':
					cfg.keepStyle = !cfg.keepStyle
				}

			case *tcell.EventResize:
				newW, newH := screen.Size()
				if newW != w || newH != h {
					w, h = newW, newH
					screen.Clear()
					screen.Sync()
				}
			}

		// ── animation tick ──
		case <-ticker.C:
			// Detect resize that wasn't caught by EventResize (some terminals).
			newW, newH := screen.Size()
			if newW != w || newH != h {
				w, h = newW, newH
				screen.Clear()
			}

			updatePipes(pipes, cfg, screen)
			screen.Show()

			count += cfg.numPipes
			if cfg.limit > 0 && count >= cfg.limit {
				screen.Clear()
				count = 0
			}
		}
	}
}
