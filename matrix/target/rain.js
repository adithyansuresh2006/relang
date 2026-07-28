/**
 * Matrix Digital Rain - Node.js Implementation
 * Ported from Python source for reLang
 */

class Matrix {
    static MATRIX_CHARS = [
        "- ", "* ", "% ", "& ", "# ", "@ ", "1 ", "2 ", "3 ", "4 ", "5 ", "6 ", "7 ", "8 ", "9 ", "0 ",
        "ア", "ィ", "イ", "ゥ", "ウ", "ェ", "エ", "ォ", "オ", "カ", "ガ", "キ", "ギ", "ク", "グ", "ケ", "ゲ", "コ",
        "ゴ", "サ", "ザ", "シ", "ジ", "ス", "ズ", "セ", "ゼ", "ソ", "ゾ", "タ", "ダ", "チ", "ヂ", "ッ", "ツ", "ヅ", "テ"
    ];

    static TERMINAL_COLOURS = ["22", "28"];

    constructor(screenWidth = 150, lineCount = 750, lineSpeed = 0.1) {
        this._screenWidth = screenWidth;
        this._lineCount = lineCount;
        this._lineSpeed = lineSpeed;
        this._lineArray = new Map();
    }

    _getRandomInt(min, max) {
        return Math.floor(Math.random() * (max - min + 1)) + min;
    }

    _getTextColourLightGreenChar() {
        return "\x1b[38;5;15m";
    }

    _getTextColourRandomChar() {
        const randomIndex = this._getRandomInt(0, 1);
        return "\x1b[38;5;" + Matrix.TERMINAL_COLOURS[randomIndex] + "m";
    }

    _getCharacter() {
        const randomIndex = this._getRandomInt(0, Matrix.MATRIX_CHARS.length - 1);
        return Matrix.MATRIX_CHARS[randomIndex];
    }

    _setScreenLineArray() {
        for (let i = 0; i < this._screenWidth; i++) {
            this._lineArray.set(i, 1);
        }
    }

    async startMatrix() {
        this._setScreenLineArray();

        for (let l = 0; l < this._lineCount; l++) {
            let line = "";

            for (const [m, n] of this._lineArray.entries()) {
                if (n === 1 || n === 2) {
                    if (n === 2) {
                        line += this._getTextColourLightGreenChar() + this._getCharacter();
                        this._lineArray.set(m, 1);
                    } else {
                        line += this._getTextColourRandomChar() + this._getCharacter();
                    }

                    if (1 === this._getRandomInt(1, 30)) {
                        this._lineArray.set(m, 0);
                    }
                } else {
                    line += this._getTextColourRandomChar() + " ";
                    if (1 === this._getRandomInt(1, 60)) {
                        this._lineArray.set(m, 2);
                    }
                }
            }

            console.log(line);
            if (this._lineSpeed > 0) {
                await new Promise(resolve => setTimeout(resolve, this._lineSpeed * 1000));
            }
        }
    }
}

if (require.main === module) {
    const matrix = new Matrix();
    matrix.startMatrix();
}

module.exports = Matrix;
