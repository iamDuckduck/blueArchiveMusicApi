package com.ba.bluearchivemusicapi.service;

import com.ba.bluearchivemusicapi.common.constant.MessageConstant;
import com.ba.bluearchivemusicapi.common.constant.SortConstant;
import com.ba.bluearchivemusicapi.common.exception.FileUploadException;
import com.ba.bluearchivemusicapi.common.exception.OstNotFoundException;
import com.ba.bluearchivemusicapi.common.exception.OstTypeNotFoundException;
import com.ba.bluearchivemusicapi.common.exception.PathNotMatchException;
import com.ba.bluearchivemusicapi.common.utils.CloudflareUtil;
import com.ba.bluearchivemusicapi.dtos.OstDTO;
import com.ba.bluearchivemusicapi.dtos.OstEditDTO;
import com.ba.bluearchivemusicapi.dtos.OstUploadDTO;
import com.ba.bluearchivemusicapi.dtos.OstPageDTO;
import com.ba.bluearchivemusicapi.entities.OST;
import com.ba.bluearchivemusicapi.entities.OstType;
import com.ba.bluearchivemusicapi.mappers.OstMapper;
import com.ba.bluearchivemusicapi.repositories.OstRepository;
import com.ba.bluearchivemusicapi.repositories.OstTypeRepository;
import com.ba.bluearchivemusicapi.specifications.OstSpecifications;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;

import java.io.IOException;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

import static com.ba.bluearchivemusicapi.common.constant.CacheConstants.*;
import static com.ba.bluearchivemusicapi.common.constant.CloudflareConstant.*;


@Service
@RequiredArgsConstructor
public class OstService {
    private final OstTypeRepository ostTypeRepository;

    private final OstRepository ostRepository;

    private final OstMapper ostMapper;

    private final CloudflareUtil cloudflareUtil;

    private final S3Client s3Client;

    @Value("${cloudflare.r2.bucket}")
    private String bucket;

    private final RedisTemplate<String, Integer> integerRedisTemplate;

    private final StringRedisTemplate stringRedisTemplate;

    @Transactional
    public void upload(OstUploadDTO ostUploadDTO) {
        // Fetch OstType by OstTypeName and null handling
        String ostTypeName = ostUploadDTO.getOstTypeName();

        OstType ostType = ostTypeRepository.findByName(ostTypeName);
        Optional.ofNullable(ostType)
                .orElseThrow(() -> new OstTypeNotFoundException(MessageConstant.OST_TYPE_NOT_FOUND));

        // get files and upload to cloud
        MultipartFile coverImage = ostUploadDTO.getImage();
        MultipartFile audio = ostUploadDTO.getAudio();

        String imageKey = uploadFileToBucket(coverImage);
        String audioKey = uploadFileToBucket(audio);

        // save the OST
        OST ost = OST.builder()
                .ostNumber(ostUploadDTO.getOstNumber())
                .name(ostUploadDTO.getName())
                .author(ostUploadDTO.getAuthor())
                .image_path(imageKey)
                .audio_path(audioKey)
                .ostType(ostType)
                .build();

        ostRepository.save(ost);
    }


    public String getImageById(Long id) {
        OST ost = ostRepository.findById(id)
                .orElseThrow(() -> new OstNotFoundException(MessageConstant.OST_NOT_FOUND));

        String publicUrlSuffix = ost.getImage_path();

        return PUBLIC_URL_PREFIX + publicUrlSuffix;
    }

    public String getAudioById(Long id) {
        // increment playCount cache first
        String playCountCacheKey = PLAYCOUNT_CACHE + "::" + id;
        integerRedisTemplate.opsForValue().increment(playCountCacheKey, 1);

        // get audioUrl cache value
        String cacheKey = AUDIO_URL_CACHE + "::" + id;
        String audioUrlCache = stringRedisTemplate.opsForValue().get(cacheKey);

        // if audioUrl cache value exists, return cached value
        if (audioUrlCache != null) {
            return audioUrlCache;
        } else {
            OST ost = ostRepository.findById(id)
                    .orElseThrow(() -> new OstNotFoundException(MessageConstant.OST_NOT_FOUND));

            // get audioUrl
            String key = ost.getAudio_path();
            String audioUrl = cloudflareUtil.generatePresignedDownloadUrl(bucket, key, OST_AUDIO_EXPIRATION);

            stringRedisTemplate.opsForValue().set(cacheKey, audioUrl, AUDIO_URL_CACHE_TTL);

            return audioUrl;
        }


    }

    public Page<OstPageDTO> pageQuery(Integer page, Integer size, String sortField, String sortDirection, String filterField, String filterValue) {
        // TODO fix warning of ration$PageModule$WarningLoggingModifier (when returning Page object)

        // map fields to corresponding entity field (e.g. ostType.name)
        sortField = mapToEntityField(sortField);
        // sortField must not be null
        if (sortField == null) {
            sortField = SortConstant.DEFAULT_SORT_FIELD;
        }

        Sort.Direction direction = sortDirection.equals(SortConstant.SORT_DIRECTION_DES) ? Sort.Direction.DESC : Sort.Direction.ASC;
        Pageable pageable = PageRequest.of(page, size, Sort.by(direction, sortField));

        filterField = mapToEntityField(filterField);
        Specification<OST> ostSpecification = OstSpecifications.byFieldAndValue(filterField, filterValue);

        Page<OST> ostResults = ostRepository.findAll(ostSpecification, pageable);
        return ostResults.map(ostMapper::toOstPageDTO);
    }

    private String mapToEntityField(String field) {
        // idea for large amount of mapping
//        for (Field classField : OST.class.getDeclaredFields()) {
//            System.out.println("Found field " + classField.getName() + " in type " + classField.getDeclaringClass());
//            fieldMapping.put(classField.getName(), classField.getName());
//        }
//
//        for (Field classField : OstType.class.getDeclaredFields()) {
//            fieldMapping.put(classField.getName(), "ostType." + classField.getName());
//        }

        Map<String, String> fieldMapping = new HashMap<>();
        fieldMapping.put("author", "author");
        fieldMapping.put("name", "name");
        fieldMapping.put("playCount", "playCount");
        fieldMapping.put("volumeName", "ostType.name");
        fieldMapping.put("volume", "ostType.volume");
        fieldMapping.put("ostNumber", "ostNumber");

        // may return null if validation of controller missed edge cases
        return fieldMapping.get(field);
    }

    public OstDTO edit(Long id, OstEditDTO ostEditDTO) {
        // Fetch OstType by OstTypeName and null handling
        String ostTypeName = ostEditDTO.getOstTypeName();

        OstType ostType = ostTypeRepository.findByName(ostTypeName);
        Optional.ofNullable(ostType)
                .orElseThrow(() -> new OstTypeNotFoundException(MessageConstant.OST_TYPE_NOT_FOUND));


        // search OST by id
        OST ost = ostRepository.findById(id)
                .orElseThrow(() -> new OstNotFoundException(MessageConstant.OST_NOT_FOUND));

        // validation for image and audio path
        if (!ostEditDTO.getImage_path().equals(ost.getImage_path()) || !ostEditDTO.getAudio_path().equals(ost.getAudio_path())) {
            throw new PathNotMatchException(MessageConstant.FILE_PATH_NOT_MATCH);
        }

        // upload image to bucket and save the path
        MultipartFile coverImage = ostEditDTO.getImage();
        if (coverImage != null) {
            String key = uploadFileToBucket(coverImage);
            ostEditDTO.setImage_path(key);
        }

        // upload audio to bucket and save the path
        MultipartFile audio = ostEditDTO.getAudio();
        if (audio != null) {
            String key = uploadFileToBucket(audio);
            ostEditDTO.setAudio_path(key);
        }

        // update the Ost
        ostMapper.updateOstFromOstEditDTO(ostEditDTO, ost);

        // save the ost
        ostRepository.save(ost);

        return ostMapper.toDTO(ost);
    }

    // only support OST audio and image for now
    private String uploadFileToBucket(MultipartFile file) {
        // create Req object to the bucket
        PutObjectRequest req = cloudflareUtil.createPutObjectReq(file);

        // todo: handle one failed, one success situation
        // save image and audio in Cloudflare bucket
        try {
            s3Client.putObject(req, RequestBody.fromBytes(file.getBytes()));
        } catch (IOException e) {
            throw new FileUploadException(MessageConstant.FAILED_FILE_UPLOAD_R2, e);
        }

        // get keys (location of the file)
        return req.key();
    }
}
