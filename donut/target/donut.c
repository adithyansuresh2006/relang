#include <stdio.h>
#include <string.h>
#include <math.h>

// Define functions for calculating sine and cosine matching reference implementation
double calculate_sin(double x) {
    return sin(x);
}

double calculate_cos(double x) {
    return cos(x);
}

// Define function for drawing the donut
void draw_donut(void) {
    double angle1 = 0.0;
    double angle2 = 0.0;
    double z_buffer[1760];
    char pixels[1761];
    const char luminance[] = ".,-~:;=!*#$@";

    // Clear the console
    printf("\033[2J");
    fflush(stdout);

    int running = 1;
    while (running) {
        // Clear the pixel and z_buffer lists
        memset(pixels, ' ', 1760);
        pixels[1760] = '\0';
        for (int k = 0; k < 1760; k++) {
            z_buffer[k] = 0.0;
        }

        // Calculate the position and brightness of each pixel
        for (int j = 0; j < 628; j += 7) {
            for (int i = 0; i < 628; i += 2) {
                double sin_i = calculate_sin(i / 100.0);
                double cos_j = calculate_cos(j / 100.0);
                double sin_angle1 = calculate_sin(angle1);
                double sin_j = calculate_sin(j / 100.0);
                double cos_angle1 = calculate_cos(angle1);
                double height = cos_j + 2.0;
                double distance = 1.0 / (sin_i * height * sin_angle1 + sin_j * cos_angle1 + 5.0);
                double cos_i = calculate_cos(i / 100.0);
                double cos_angle2 = calculate_cos(angle2);
                double sin_angle2 = calculate_sin(angle2);
                double sin_height = sin_i * height * cos_angle1 - sin_j * sin_angle1;

                int x = (int)(40 + 30 * distance * (cos_i * height * cos_angle2 - sin_height * sin_angle2));
                int y = (int)(12 + 15 * distance * (cos_i * height * sin_angle2 + sin_height * cos_angle2));
                int index = x + 80 * y;
                int brightness = (int)(8 * ((sin_j * sin_angle1 - sin_i * cos_j * cos_angle1) * cos_angle2 - sin_i * cos_j * sin_angle1 - sin_j * cos_angle1 - cos_i * cos_j * sin_angle2));

                if (y >= 0 && y < 22 && x >= 0 && x < 80 && distance > z_buffer[index]) {
                    z_buffer[index] = distance;
                    int b_idx = brightness > 0 ? brightness : 0;
                    if (b_idx > 11) b_idx = 11;
                    pixels[index] = luminance[b_idx];
                }
            }
        }

        // Print the pixels to the console
        printf("\033[H%s", pixels);
        fflush(stdout);

        // Update the angles for the next iteration
        angle1 += 0.30;
        angle2 += 0.15;
    }
}

int main(void) {
    draw_donut();
    return 0;
}
