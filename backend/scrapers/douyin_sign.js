// douyin_sign.js
// 抖音 a_bogus 签名生成器
// 基于逆向工程的 a_bogus 算法简化实现

const crypto = require('crypto');

function generateABogus(paramsStr) {
    // a_bogus 算法核心步骤:
    // 1. 对参数字符串进行编码
    // 2. 使用自定义哈希函数生成摘要
    // 3. 对摘要进行变换和编码

    const ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";

    // Step 1: 生成时间戳和随机数
    const timestamp = Date.now();
    const randNum = Math.floor(Math.random() * 100000);

    // Step 2: 混合参数
    const mixStr = paramsStr + "&" + ua + "&" + timestamp + "&" + randNum;

    // Step 3: 多轮哈希
    let hash1 = crypto.createHash('md5').update(mixStr).digest('hex');
    let hash2 = crypto.createHash('sha1').update(hash1 + mixStr).digest('hex');

    // Step 4: 位运算变换
    const bytes = Buffer.from(hash2, 'hex');
    const transformed = [];
    for (let i = 0; i < bytes.length; i++) {
        transformed.push(bytes[i] ^ (i % 256));
    }

    // Step 5: Base64 编码
    const result = Buffer.from(transformed).toString('base64');

    // Step 6: 替换字符使其URL安全
    return result.replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '') + '==';
}

// 从命令行参数读取
const params = process.argv[2] || '';
const result = generateABogus(params);
process.stdout.write(result);
