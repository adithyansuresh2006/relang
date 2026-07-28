package main

import (
	"fmt"
	"image"
	"image/color"
	_ "image/gif"
	_ "image/jpeg"
	_ "image/png"
	"math"
	"os"
	"strconv"
	"strings"
)

const (
	GrayScaleFlag = 1 << 0
	ReverseFlag   = 1 << 1
	PrintFlag     = 1 << 2
	DebugFlag     = 1 << 3
)

const DefaultChars = "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,\"^`'. "

func showUsage() {
	fmt.Printf(
		"\nUsage: \x1b[1mimg2ascii [options] -i <FILE> [-o <FILE>]\x1b[0m \n\n" +
			"A command-line tool for converting images to ASCII art \n\n" +
			"Options: \n" +
			"   -i, --input  <FILE>     Path of the input image file (required) \n" +
			"   -o, --output <FILE>     Path of the output file \n" +
			"   -w, --width  <NUMBER>   Width of the output \n" +
			"   -c, --chars  <STRING>   Characters to be used for the ASCII image \n" +
			"   -p, --print             Print the output to the console \n" +
			"   -r, --reverse           Reverse the string of characters \n" +
			"   -d, --debug             Print some useful information \n\n",
	)
}

func reverseString(s string) string {
	runes := []rune(s)
	n := len(runes)
	for i := 0; i < n/2; i++ {
		runes[i], runes[n-1-i] = runes[n-1-i], runes[i]
	}
	return string(runes)
}

func parseArgs(args []string) (string, string, string, int, uint8, bool) {
	if len(args) == 0 {
		fmt.Printf("No input file\n")
		showUsage()
		os.Exit(1)
	}

	var inputFilePath string
	var outputFilePath string
	characters := DefaultChars
	desiredWidth := 0
	var flags uint8
	resizeImage := false

	i := 0
	for i < len(args) {
		arg := args[i]
		if arg == "-h" || arg == "--help" {
			showUsage()
			os.Exit(1)
		} else if arg == "-i" || arg == "--input" {
			if i+1 < len(args) {
				inputFilePath = args[i+1]
				i += 2
				continue
			} else {
				fmt.Printf("\nHint: Use the \x1b[1m--help\x1b[0m option to get help about the usage \n\n")
				os.Exit(1)
			}
		} else if strings.HasPrefix(arg, "-i=") || strings.HasPrefix(arg, "--input=") {
			parts := strings.SplitN(arg, "=", 2)
			inputFilePath = parts[1]
			i++
			continue
		} else if arg == "-o" || arg == "--output" {
			if i+1 < len(args) {
				outputFilePath = args[i+1]
				i += 2
				continue
			} else {
				fmt.Printf("\nHint: Use the \x1b[1m--help\x1b[0m option to get help about the usage \n\n")
				os.Exit(1)
			}
		} else if strings.HasPrefix(arg, "-o=") || strings.HasPrefix(arg, "--output=") {
			parts := strings.SplitN(arg, "=", 2)
			outputFilePath = parts[1]
			i++
			continue
		} else if arg == "-w" || arg == "--width" {
			if i+1 < len(args) {
				w, err := strconv.Atoi(args[i+1])
				if err == nil {
					desiredWidth = w
				}
				resizeImage = true
				i += 2
				continue
			} else {
				fmt.Printf("\nHint: Use the \x1b[1m--help\x1b[0m option to get help about the usage \n\n")
				os.Exit(1)
			}
		} else if strings.HasPrefix(arg, "-w=") || strings.HasPrefix(arg, "--width=") {
			parts := strings.SplitN(arg, "=", 2)
			w, err := strconv.Atoi(parts[1])
			if err == nil {
				desiredWidth = w
			}
			resizeImage = true
			i++
			continue
		} else if arg == "-c" || arg == "--chars" {
			if i+1 < len(args) {
				if len(args[i+1]) > 0 {
					characters = args[i+1]
				}
				i += 2
				continue
			} else {
				fmt.Printf("\nHint: Use the \x1b[1m--help\x1b[0m option to get help about the usage \n\n")
				os.Exit(1)
			}
		} else if strings.HasPrefix(arg, "-c=") || strings.HasPrefix(arg, "--chars=") {
			parts := strings.SplitN(arg, "=", 2)
			if len(parts[1]) > 0 {
				characters = parts[1]
			}
			i++
			continue
		} else if arg == "-g" || arg == "--grayscale" {
			flags |= GrayScaleFlag
			i++
			continue
		} else if arg == "-p" || arg == "--print" {
			flags |= PrintFlag
			i++
			continue
		} else if arg == "-r" || arg == "--reverse" {
			flags |= ReverseFlag
			i++
			continue
		} else if arg == "-d" || arg == "--debug" {
			flags |= DebugFlag
			i++
			continue
		} else if strings.HasPrefix(arg, "-") && !strings.HasPrefix(arg, "--") && len(arg) > 1 {
			j := 1
			valid := true
			for j < len(arg) {
				ch := arg[j]
				if ch == 'h' {
					showUsage()
					os.Exit(1)
				} else if ch == 'g' {
					flags |= GrayScaleFlag
				} else if ch == 'p' {
					flags |= PrintFlag
				} else if ch == 'r' {
					flags |= ReverseFlag
				} else if ch == 'd' {
					flags |= DebugFlag
				} else if ch == 'i' || ch == 'o' || ch == 'w' || ch == 'c' {
					var val string
					if j+1 < len(arg) {
						val = arg[j+1:]
						j = len(arg)
					} else if i+1 < len(args) {
						val = args[i+1]
						i++
					} else {
						fmt.Printf("\nHint: Use the \x1b[1m--help\x1b[0m option to get help about the usage \n\n")
						os.Exit(1)
					}
					if ch == 'i' {
						inputFilePath = val
					} else if ch == 'o' {
						outputFilePath = val
					} else if ch == 'w' {
						w, err := strconv.Atoi(val)
						if err == nil {
							desiredWidth = w
						}
						resizeImage = true
					} else if ch == 'c' {
						if len(val) > 0 {
							characters = val
						}
					}
				} else {
					valid = false
					break
				}
				j++
			}
			if !valid {
				fmt.Printf("\nHint: Use the \x1b[1m--help\x1b[0m option to get help about the usage \n\n")
				os.Exit(1)
			}
			i++
			continue
		} else if strings.HasPrefix(arg, "-") {
			fmt.Printf("\nHint: Use the \x1b[1m--help\x1b[0m option to get help about the usage \n\n")
			os.Exit(1)
		} else {
			i++
		}
	}

	if inputFilePath == "" {
		fmt.Printf("No input file\n")
		showUsage()
		os.Exit(1)
	}

	if outputFilePath == "" {
		flags |= PrintFlag
	}

	return inputFilePath, outputFilePath, characters, desiredWidth, flags, resizeImage
}

type RGB struct {
	R, G, B uint8
}

func loadImage(inputPath string, desiredWidth *int, desiredHeight *int, resizeImage *bool) ([]RGB, int, int) {
	file, err := os.Open(inputPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Could not load image \n")
		os.Exit(1)
	}
	defer file.Close()

	img, _, err := image.Decode(file)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Could not load image \n")
		os.Exit(1)
	}

	bounds := img.Bounds()
	origWidth := bounds.Dx()
	origHeight := bounds.Dy()

	if *resizeImage {
		if *desiredWidth <= 0 {
			fmt.Fprintf(os.Stderr, "Argument 'width' must be greater than 0 \n")
			os.Exit(1)
		} else if *desiredWidth > origWidth {
			fmt.Fprintf(os.Stderr, "Argument 'width' can not be greater than the original image width (%dpx) \n", origWidth)
			os.Exit(1)
		}
		*desiredHeight = int(float64(origHeight) / (float64(origWidth) / float64(*desiredWidth)) / 2.0)
	} else {
		*desiredWidth = origWidth
		*desiredHeight = origHeight / 2
	}

	w := *desiredWidth
	h := *desiredHeight

	// Extract original pixels into RGB grid
	origPixels := make([]RGB, origWidth*origHeight)
	for y := 0; y < origHeight; y++ {
		for x := 0; x < origWidth; x++ {
			c := img.At(bounds.Min.X+x, bounds.Min.Y+y)
			var r, g, b uint8
			switch col := c.(type) {
			case color.NRGBA:
				r, g, b = col.R, col.G, col.B
			case color.NRGBA64:
				r, g, b = uint8(col.R>>8), uint8(col.G>>8), uint8(col.B>>8)
			case color.RGBA:
				r, g, b = col.R, col.G, col.B
			case color.RGBA64:
				r, g, b = uint8(col.R>>8), uint8(col.G>>8), uint8(col.B>>8)
			case color.Alpha:
				r, g, b = col.A, col.A, col.A
			case color.Alpha16:
				a := uint8(col.A >> 8)
				r, g, b = a, a, a
			case color.Gray:
				r, g, b = col.Y, col.Y, col.Y
			case color.Gray16:
				yVal := uint8(col.Y >> 8)
				r, g, b = yVal, yVal, yVal
			default:
				cr, cg, cb, _ := c.RGBA()
				r, g, b = uint8(cr>>8), uint8(cg>>8), uint8(cb>>8)
			}
			origPixels[y*origWidth+x] = RGB{R: r, G: g, B: b}
		}
	}

	return resampleMitchell(origPixels, origWidth, origHeight, w, h), w, h
}

func mitchellFilter(x float64) float64 {
	x = math.Abs(x)
	if x < 1.0 {
		return (7.0/6.0)*x*x*x - 2.0*x*x + (8.0 / 9.0)
	} else if x < 2.0 {
		return (-7.0/18.0)*x*x*x + 2.0*x*x - (10.0/3.0)*x + (16.0 / 9.0)
	}
	return 0.0
}

func resampleMitchell(origPixels []RGB, srcW, srcH, dstW, dstH int) []RGB {
	scaleX := float64(srcW) / float64(dstW)
	scaleY := float64(srcH) / float64(dstH)

	radX := 2.0
	if scaleX > 1.0 {
		radX = 2.0 * scaleX
	}

	// Pass 1: Horizontal resample (srcW x srcH -> dstW x srcH)
	tmp := make([]RGB, dstW*srcH)
	for y := 0; y < srcH; y++ {
		rowOffset := y * srcW
		tmpOffset := y * dstW
		for x := 0; x < dstW; x++ {
			cx := (float64(x)+0.5)*scaleX - 0.5
			minX := int(math.Floor(cx - radX))
			maxX := int(math.Ceil(cx + radX))

			var sumR, sumG, sumB, totalW float64
			for sx := minX; sx <= maxX; sx++ {
				dist := (float64(sx) - cx)
				if scaleX > 1.0 {
					dist /= scaleX
				}
				w := mitchellFilter(dist)
				if w == 0 {
					continue
				}
				clampedSX := sx
				if clampedSX < 0 {
					clampedSX = 0
				} else if clampedSX >= srcW {
					clampedSX = srcW - 1
				}
				p := origPixels[rowOffset+clampedSX]
				sumR += float64(p.R) * w
				sumG += float64(p.G) * w
				sumB += float64(p.B) * w
				totalW += w
			}

			if totalW > 0 {
				r := math.Max(0, math.Min(255, math.Round(sumR/totalW)))
				g := math.Max(0, math.Min(255, math.Round(sumG/totalW)))
				b := math.Max(0, math.Min(255, math.Round(sumB/totalW)))
				tmp[tmpOffset+x] = RGB{R: uint8(r), G: uint8(g), B: uint8(b)}
			}
		}
	}

	// Pass 2: Vertical resample (dstW x srcH -> dstW x dstH)
	radY := 2.0
	if scaleY > 1.0 {
		radY = 2.0 * scaleY
	}

	dst := make([]RGB, dstW*dstH)
	for x := 0; x < dstW; x++ {
		for y := 0; y < dstH; y++ {
			cy := (float64(y)+0.5)*scaleY - 0.5
			minY := int(math.Floor(cy - radY))
			maxY := int(math.Ceil(cy + radY))

			var sumR, sumG, sumB, totalW float64
			for sy := minY; sy <= maxY; sy++ {
				dist := (float64(sy) - cy)
				if scaleY > 1.0 {
					dist /= scaleY
				}
				w := mitchellFilter(dist)
				if w == 0 {
					continue
				}
				clampedSY := sy
				if clampedSY < 0 {
					clampedSY = 0
				} else if clampedSY >= srcH {
					clampedSY = srcH - 1
				}
				p := tmp[clampedSY*dstW+x]
				sumR += float64(p.R) * w
				sumG += float64(p.G) * w
				sumB += float64(p.B) * w
				totalW += w
			}

			if totalW > 0 {
				r := math.Max(0, math.Min(255, math.Round(sumR/totalW)))
				g := math.Max(0, math.Min(255, math.Round(sumG/totalW)))
				b := math.Max(0, math.Min(255, math.Round(sumB/totalW)))
				dst[y*dstW+x] = RGB{R: uint8(r), G: uint8(g), B: uint8(b)}
			}
		}
	}

	return dst
}

func getIntensity(pixel RGB) uint8 {
	return uint8(math.Round(0.299*float64(pixel.R) + 0.587*float64(pixel.G) + 0.114*float64(pixel.B)))
}

func getOutputGrayscale(image []RGB, width int, height int, characters string, flags uint8) string {
	if (flags & ReverseFlag) != 0 {
		characters = reverseString(characters)
	}

	charRunes := []rune(characters)
	charCount := len(charRunes)
	step := 255.0 / float64(charCount-1)

	var sb strings.Builder
	total := width * height

	for i := 0; i < total; i++ {
		intensity := getIntensity(image[i])
		charIndex := int(float64(intensity) / step)
		if charIndex >= charCount {
			charIndex = charCount - 1
		}

		sb.WriteRune(charRunes[charIndex])

		if (i+1)%width == 0 {
			sb.WriteByte('\n')
		}
	}

	return sb.String()
}

func getOutputRGB(image []RGB, width int, height int, characters string, flags uint8) string {
	if (flags & ReverseFlag) != 0 {
		characters = reverseString(characters)
	}

	charRunes := []rune(characters)
	charCount := len(charRunes)
	step := 255.0 / float64(charCount-1)

	var sb strings.Builder
	total := width * height

	var rPrev, gPrev, bPrev uint8
	first := true

	for i := 0; i < total; i++ {
		pixel := image[i]
		intensity := getIntensity(pixel)
		charIndex := int(float64(intensity) / step)
		if charIndex >= charCount {
			charIndex = charCount - 1
		}

		if first || !(pixel.R == rPrev && pixel.G == gPrev && pixel.B == bPrev) {
			sb.WriteString(fmt.Sprintf("\x1b[38;2;%d;%d;%dm", pixel.R, pixel.G, pixel.B))
			rPrev = pixel.R
			gPrev = pixel.G
			bPrev = pixel.B
			first = false
		}

		sb.WriteRune(charRunes[charIndex])

		if (i+1)%width == 0 {
			sb.WriteByte('\n')
		}
	}

	sb.WriteString("\x1b[0m")
	return sb.String()
}

func writeOutput(
	image []RGB,
	inputFilePath string,
	outputFilePath string,
	characters string,
	width int,
	height int,
	flags uint8,
) {
	var output string
	if (flags & GrayScaleFlag) != 0 {
		output = getOutputGrayscale(image, width, height, characters, flags)
	} else {
		output = getOutputRGB(image, width, height, characters, flags)
	}

	if (flags & DebugFlag) != 0 {
		outDest := outputFilePath
		if outDest == "" {
			outDest = "stdout"
		}
		fmt.Printf(
			"Input: %s \n"+
				"Output: %s \n"+
				"Resolution: %dx%d \n"+
				"Characters (%d): \"%s\" \n",
			inputFilePath,
			outDest,
			width, height,
			len([]rune(characters)), characters,
		)
	}

	if (flags & PrintFlag) != 0 {
		fmt.Print(output)
	}

	if outputFilePath != "" {
		err := os.WriteFile(outputFilePath, []byte(output), 0644)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Could not create an output file: %s \n", err)
			os.Exit(1)
		}
	}
}

func main() {
	args := os.Args[1:]
	inputFilePath, outputFilePath, characters, desiredWidth, flags, resizeImage := parseArgs(args)

	desiredHeight := 0
	imagePixels, w, h := loadImage(inputFilePath, &desiredWidth, &desiredHeight, &resizeImage)

	writeOutput(
		imagePixels,
		inputFilePath,
		outputFilePath,
		characters,
		w,
		h,
		flags,
	)
}
